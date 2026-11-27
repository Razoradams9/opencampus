"""Institution registry and tenant-scoped membership management.

Every tenant-scoped query below filters on institution_id explicitly *and*
runs under RLS. The explicit filter is the primary control; RLS is the
backstop that still holds if a query forgets the filter.
"""

import uuid

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import ApiError, forbidden
from app.db.session import set_db_context
from app.models import Institution, Membership, MembershipRole, MembershipStatus, User
from app.schemas.institution import InstitutionCreate, InstitutionUpdate, MemberOut, MemberUpdate


def get_by_slug(db: Session, slug: str) -> Institution:
    institution = db.scalar(select(Institution).where(Institution.slug == slug.strip().lower()))
    if institution is None:
        raise ApiError(404, "institution_not_found", "Institution not found")
    return institution


def create(db: Session, data: InstitutionCreate) -> Institution:
    institution = Institution(
        slug=data.slug,
        name=data.name.strip(),
        allow_self_registration=data.allow_self_registration,
        timezone=data.timezone,
    )
    db.add(institution)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise ApiError(409, "slug_taken", "An institution with this slug already exists") from None
    return institution


def update(db: Session, slug: str, data: InstitutionUpdate) -> Institution:
    institution = get_by_slug(db, slug)
    if data.status is not None:
        institution.status = data.status
    if data.allow_self_registration is not None:
        institution.allow_self_registration = data.allow_self_registration
    if data.timezone is not None:
        institution.timezone = data.timezone
    db.commit()
    return institution


def provision_college_admin(db: Session, slug: str, email: str) -> Membership:
    """Platform-admin operation. The tenant context is set to the *target*
    institution only after the caller's platform role has been verified."""
    institution = get_by_slug(db, slug)
    user = db.scalar(select(User).where(User.email == email.strip().lower()))
    if user is None:
        raise ApiError(404, "user_not_found", "No user with that email; they must register first")

    set_db_context(db, tenant_id=institution.id, user_id=None)
    membership = db.scalar(
        select(Membership).where(Membership.institution_id == institution.id, Membership.user_id == user.id)
    )
    if membership is None:
        membership = Membership(institution_id=institution.id, user_id=user.id)
        db.add(membership)
    membership.role = MembershipRole.college_admin
    membership.status = MembershipStatus.active
    db.commit()
    return membership


def list_members(db: Session, institution_id: uuid.UUID) -> list[MemberOut]:
    rows = db.execute(
        select(Membership, User)
        .join(User, User.id == Membership.user_id)
        .where(Membership.institution_id == institution_id)
        .order_by(User.full_name)
    )
    return [
        MemberOut(
            membership_id=m.id, user_id=u.id, full_name=u.full_name, email=u.email, role=m.role, status=m.status
        )
        for m, u in rows
    ]


def update_member(
    db: Session, institution_id: uuid.UUID, actor_user_id: uuid.UUID, membership_id: uuid.UUID, data: MemberUpdate
) -> MemberOut:
    membership = db.scalar(
        select(Membership).where(Membership.id == membership_id, Membership.institution_id == institution_id)
    )
    if membership is None:
        raise ApiError(404, "member_not_found", "Member not found")
    if membership.user_id == actor_user_id:
        raise forbidden("cannot_modify_self", "You cannot change your own membership")
    if membership.role == MembershipRole.college_admin:
        raise forbidden("cannot_modify_admin", "College administrators are managed by platform administrators")

    if data.role is not None:
        membership.role = MembershipRole(data.role)
    if data.status is not None:
        membership.status = data.status
    db.commit()
    user = db.get(User, membership.user_id)
    assert user is not None
    return MemberOut(
        membership_id=membership.id,
        user_id=user.id,
        full_name=user.full_name,
        email=user.email,
        role=membership.role,
        status=membership.status,
    )
