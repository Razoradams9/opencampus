import uuid
from fastapi import APIRouter

from app.api.deps import CollegeAdmin, CurrentTenant, DbSession
from app.schemas.institution import CurrentInstitution, InstitutionOut, InstitutionPublic, MemberOut, MemberUpdate
from app.services import institutions as service

# Public directory: lookup by slug, e.g. to confirm the college on the sign-up form.
public_router = APIRouter(prefix="/institutions", tags=["institutions"])

# Current tenant: everything here is scoped to the session's active institution.
tenant_router = APIRouter(prefix="/institution", tags=["institution"])

@public_router.get("/{slug}", response_model=InstitutionPublic)
def lookup(slug: str, db: DbSession):
    institution = service.get_by_slug(db, slug)
    return InstitutionPublic(
        slug=institution.slug,
        name=institution.name,
        status=institution.status,
        registration_open=institution.allow_self_registration and institution.status == "active",
    )


@tenant_router.get("", response_model=CurrentInstitution)
def current(tenant: CurrentTenant):
    return CurrentInstitution(institution=InstitutionOut.model_validate(tenant.institution, from_attributes=True), role=tenant.role)


@tenant_router.get("/members", response_model=list[MemberOut])
def members(tenant: CollegeAdmin, db: DbSession):
    return service.list_members(db, tenant.institution_id)


@tenant_router.patch("/members/{membership_id}", response_model=MemberOut)
def update_member(membership_id: uuid.UUID, body: MemberUpdate, tenant: CollegeAdmin, db: DbSession):
    return service.update_member(db, tenant.institution_id, tenant.user.id, membership_id, body)
