"""Security boundaries, applied as FastAPI dependencies.

    get_principal      valid access token + live session          -> 401
    get_tenant         active membership in the session's tenant  -> 403
    require_roles(...) membership role, read from the database    -> 403
    require_platform_admin  user flag, read from the database     -> 403

The tenant always comes from the server-side session row, never from a
request parameter, and the role always comes from the membership row.
"""

import uuid
from collections.abc import Callable
from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.errors import forbidden, unauthorized
from app.core.security import TokenError, constant_time_equals, decode_access_token, utcnow
from app.db.session import get_db, set_db_context
from app.models import AuthSession, Institution, InstitutionStatus, Membership, MembershipRole, MembershipStatus, User

DbSession = Annotated[Session, Depends(get_db)]
AppSettings = Annotated[Settings, Depends(get_settings)]


@dataclass
class Principal:
    user: User
    session: AuthSession


@dataclass
class TenantContext:
    user: User
    session: AuthSession
    institution: Institution
    membership: Membership

    @property
    def institution_id(self) -> uuid.UUID:
        return self.institution.id

    @property
    def role(self) -> MembershipRole:
        return self.membership.role


def get_principal(request: Request, db: DbSession, settings: AppSettings) -> Principal:
    scheme, _, token = request.headers.get("authorization", "").partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise unauthorized()
    try:
        claims = decode_access_token(settings, token)
    except TokenError:
        raise unauthorized("token_invalid", "Access token is invalid or expired") from None

    # The session lookup makes logout/revocation effective immediately.
    session = db.get(AuthSession, claims.session_id)
    if (
        session is None
        or session.user_id != claims.user_id
        or session.revoked_at is not None
        or session.expires_at <= utcnow()
        or not session.user.is_active
    ):
        raise unauthorized("session_invalid", "Session has ended")

    set_db_context(db, user_id=session.user_id)
    return Principal(user=session.user, session=session)


CurrentPrincipal = Annotated[Principal, Depends(get_principal)]


def get_tenant(principal: CurrentPrincipal, db: DbSession) -> TenantContext:
    institution_id = principal.session.active_institution_id
    if institution_id is None:
        raise forbidden("tenant_required", "No institution is selected for this session")

    set_db_context(db, tenant_id=institution_id, user_id=principal.user.id)
    membership = db.scalar(
        select(Membership).where(Membership.institution_id == institution_id, Membership.user_id == principal.user.id)
    )
    if (
        membership is None
        or membership.status != MembershipStatus.active
        or membership.institution.status != InstitutionStatus.active
    ):
        raise forbidden("tenant_access_denied", "You no longer have access to this institution")

    return TenantContext(principal.user, principal.session, membership.institution, membership)


CurrentTenant = Annotated[TenantContext, Depends(get_tenant)]


def require_roles(*roles: MembershipRole) -> Callable[[TenantContext], TenantContext]:
    allowed = frozenset(roles)

    def dependency(tenant: CurrentTenant) -> TenantContext:
        if tenant.role not in allowed:
            raise forbidden("insufficient_role", "Your role does not allow this action")
        return tenant

    return dependency


def require_platform_admin(principal: CurrentPrincipal) -> Principal:
    if not principal.user.is_platform_admin:
        raise forbidden("platform_admin_required", "Platform administrator access required")
    return principal


PlatformAdmin = Annotated[Principal, Depends(require_platform_admin)]


def verify_csrf(request: Request, settings: AppSettings) -> None:
    """Double-submit check for the cookie-authenticated endpoints (refresh,
    logout): the X-CSRF-Token header must match the CSRF cookie. A cross-site
    page cannot read the cookie, so it cannot forge the header."""
    origin = request.headers.get("origin")
    if origin is not None and origin not in settings.cors_origins and origin != str(request.base_url).rstrip("/"):
        raise forbidden("origin_rejected", "Request origin is not allowed")
    cookie = request.cookies.get(settings.csrf_cookie_name, "")
    header = request.headers.get("x-csrf-token", "")
    if not cookie or not header or not constant_time_equals(cookie, header):
        raise forbidden("csrf_failed", "CSRF validation failed")
