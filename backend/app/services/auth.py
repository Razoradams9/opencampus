"""Registration, login, refresh rotation and session revocation."""

import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.errors import ApiError, forbidden, unauthorized
from app.core.security import (
    create_access_token,
    hash_password,
    hash_refresh_token,
    new_opaque_token,
    password_needs_rehash,
    utcnow,
    verify_password,
)
from app.db.session import set_db_context
from app.models import (
    AuthSession,
    Institution,
    InstitutionStatus,
    Membership,
    MembershipRole,
    MembershipStatus,
    RefreshToken,
    User,
)
from app.schemas.auth import (
    ActiveInstitution,
    InstitutionRef,
    LoginRequest,
    MeResponse,
    MembershipOut,
    RegisterRequest,
    UserOut,
)


@dataclass
class IssuedTokens:
    session: AuthSession
    access_token: str
    refresh_token: str


def normalise_email(email: str) -> str:
    return email.strip().lower()


def _usable_memberships(db: Session, user_id: uuid.UUID) -> list[Membership]:
    """Active memberships in active institutions. Requires app.user_id context."""
    return list(
        db.scalars(
            select(Membership)
            .join(Membership.institution)
            .where(
                Membership.user_id == user_id,
                Membership.status == MembershipStatus.active,
                Institution.status == InstitutionStatus.active,
            )
            .order_by(Membership.created_at)
        )
    )


def _start_session(
    db: Session, settings: Settings, user: User, institution_id: uuid.UUID | None, user_agent: str | None
) -> IssuedTokens:
    now = utcnow()
    session = AuthSession(
        user_id=user.id,
        active_institution_id=institution_id,
        user_agent=(user_agent or "")[:400] or None,
        expires_at=now + timedelta(seconds=settings.session_max_age),
    )
    db.add(session)
    db.flush()
    refresh = _issue_refresh_token(db, settings, session, now)
    return IssuedTokens(session, create_access_token(settings, user.id, session.id, now), refresh)


def _issue_refresh_token(db: Session, settings: Settings, session: AuthSession, now: datetime) -> str:
    raw = new_opaque_token()
    db.add(
        RefreshToken(
            session_id=session.id,
            token_hash=hash_refresh_token(raw),
            expires_at=min(now + timedelta(seconds=settings.refresh_token_ttl), session.expires_at),
        )
    )
    return raw


def _open_institution(db: Session, settings: Settings) -> Institution | None:
    """The shared institution for sign-ups without a code. Created on first use
    (from configuration only, never from request input)."""
    slug = settings.open_registration_slug
    if not slug:
        return None
    db.execute(
        pg_insert(Institution)
        .values(slug=slug, name=settings.open_registration_name, allow_self_registration=True)
        .on_conflict_do_nothing(index_elements=["slug"])
    )
    return db.scalar(select(Institution).where(Institution.slug == slug))


def register(db: Session, settings: Settings, data: RegisterRequest, user_agent: str | None) -> IssuedTokens:
    if data.institution_slug:
        institution = db.scalar(select(Institution).where(Institution.slug == data.institution_slug))
    else:
        institution = _open_institution(db, settings)
        if institution is None:
            raise ApiError(400, "institution_required", "Enter the institution code your college gave you")
    # An administrator can still close or suspend the open institution.
    if (
        institution is None
        or institution.status != InstitutionStatus.active
        or not institution.allow_self_registration
    ):
        raise ApiError(400, "registration_closed", "Registration is not open for this institution")

    email = normalise_email(data.email)
    if db.scalar(select(User.id).where(User.email == email)) is not None:
        raise ApiError(409, "email_taken", "An account with this email already exists")

    user = User(email=email, password_hash=hash_password(data.password), full_name=data.full_name)
    db.add(user)
    try:
        db.flush()
    except IntegrityError:  # concurrent registration with the same email
        db.rollback()
        raise ApiError(409, "email_taken", "An account with this email already exists") from None

    # Public registration always yields a student membership; the role is not
    # an input. The insert is checked by RLS against this tenant context.
    set_db_context(db, tenant_id=institution.id, user_id=user.id)
    db.add(Membership(institution_id=institution.id, user_id=user.id, role=MembershipRole.student))
    db.flush()

    tokens = _start_session(db, settings, user, institution.id, user_agent)
    db.commit()
    return tokens


def login(db: Session, settings: Settings, data: LoginRequest, user_agent: str | None) -> IssuedTokens:
    user = db.scalar(select(User).where(User.email == normalise_email(data.email)))
    # verify_password runs a full Argon2 check even when the user is unknown.
    password_ok = verify_password(user.password_hash if user else None, data.password)
    if user is None or not password_ok or not user.is_active:
        raise unauthorized("invalid_credentials", "Invalid email or password")

    if password_needs_rehash(user.password_hash):
        user.password_hash = hash_password(data.password)

    set_db_context(db, user_id=user.id)
    memberships = _usable_memberships(db, user.id)
    chosen: Membership | None = memberships[0] if memberships else None
    if data.institution_slug:
        slug = data.institution_slug.strip().lower()
        chosen = next((m for m in memberships if m.institution.slug == slug), None)
        if chosen is None:
            raise forbidden("not_a_member", "You do not have access to that institution")

    user.last_login_at = utcnow()
    tokens = _start_session(db, settings, user, chosen.institution_id if chosen else None, user_agent)
    db.commit()
    return tokens


def _find_refresh(db: Session, raw: str) -> RefreshToken | None:
    # Row lock serialises concurrent refreshes of the same token.
    return db.scalar(
        select(RefreshToken)
        .where(RefreshToken.token_hash == hash_refresh_token(raw))
        .with_for_update(of=RefreshToken)
    )


def _revoke(session: AuthSession, reason: str) -> None:
    if session.revoked_at is None:
        session.revoked_at = utcnow()
        session.revoke_reason = reason


def rotate_refresh_token(db: Session, settings: Settings, raw: str | None) -> IssuedTokens:
    if not raw:
        raise unauthorized("refresh_missing", "No refresh token")
    row = _find_refresh(db, raw)
    if row is None:
        raise unauthorized("refresh_invalid", "Refresh token is invalid")

    session = row.session
    now = utcnow()

    if row.rotated_at is not None:
        if now - row.rotated_at <= timedelta(seconds=settings.refresh_reuse_grace):
            # Benign race (two tabs refreshing at once): the cookie has already
            # been replaced. Tell the client to retry; do not revoke.
            raise unauthorized("refresh_superseded", "Refresh token was just rotated; retry")
        # An old token replayed after the grace window suggests theft:
        # revoke the whole session (all its tokens) and force re-login.
        _revoke(session, "refresh_reuse")
        db.commit()
        raise unauthorized("refresh_reused", "Refresh token reuse detected; session revoked")

    if (
        session.revoked_at is not None
        or session.expires_at <= now
        or row.expires_at <= now
        or not session.user.is_active
    ):
        raise unauthorized("session_expired", "Session has expired or was revoked")

    row.rotated_at = now
    session.last_seen_at = now
    new_raw = _issue_refresh_token(db, settings, session, now)
    tokens = IssuedTokens(session, create_access_token(settings, session.user_id, session.id, now), new_raw)
    db.commit()
    return tokens


def logout(db: Session, raw: str | None) -> None:
    """Revokes the session behind a refresh token. Idempotent."""
    if not raw:
        return
    row = _find_refresh(db, raw)
    if row is not None:
        _revoke(row.session, "logout")
        db.commit()


def list_sessions(db: Session, user_id: uuid.UUID) -> list[AuthSession]:
    return list(
        db.scalars(
            select(AuthSession)
            .where(AuthSession.user_id == user_id, AuthSession.revoked_at.is_(None), AuthSession.expires_at > utcnow())
            .order_by(AuthSession.last_seen_at.desc())
        )
    )


def revoke_session(db: Session, user_id: uuid.UUID, session_id: uuid.UUID) -> None:
    session = db.get(AuthSession, session_id)
    # Same response for "not yours" and "does not exist".
    if session is None or session.user_id != user_id:
        raise ApiError(404, "session_not_found", "Session not found")
    _revoke(session, "user_revoked")
    db.commit()


def switch_institution(db: Session, session: AuthSession, institution_id: uuid.UUID) -> None:
    membership = next((m for m in _usable_memberships(db, session.user_id) if m.institution_id == institution_id), None)
    if membership is None:
        raise forbidden("not_a_member", "You do not have access to that institution")
    session.active_institution_id = institution_id
    db.commit()


def build_me(db: Session, user: User, session: AuthSession) -> MeResponse:
    set_db_context(db, tenant_id=db.info.get("tenant_id"), user_id=user.id)
    memberships = list(
        db.scalars(select(Membership).where(Membership.user_id == user.id).order_by(Membership.created_at))
    )
    usable = {m.institution_id for m in _usable_memberships(db, user.id)}

    def ref(institution: Institution) -> InstitutionRef:
        return InstitutionRef(id=institution.id, slug=institution.slug, name=institution.name, status=institution.status)

    active = next(
        (m for m in memberships if m.institution_id == session.active_institution_id and m.institution_id in usable), None
    )
    return MeResponse(
        user=UserOut(id=user.id, email=user.email, full_name=user.full_name, is_platform_admin=user.is_platform_admin),
        active_institution=ActiveInstitution(**ref(active.institution).model_dump(), role=active.role) if active else None,
        memberships=[MembershipOut(id=m.id, role=m.role, status=m.status, institution=ref(m.institution)) for m in memberships],
    )
