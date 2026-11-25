from fastapi import APIRouter, status

from app.api.deps import DbSession, PlatformAdmin
from app.schemas.institution import InstitutionCreate, InstitutionOut, InstitutionUpdate, MemberOut, ProvisionAdminRequest
from app.services import institutions as service

router = APIRouter(prefix="/platform", tags=["platform"])


@router.post("/institutions", status_code=status.HTTP_201_CREATED, response_model=InstitutionOut)
def create_institution(body: InstitutionCreate, _: PlatformAdmin, db: DbSession):
    return service.create(db, body)


@router.patch("/institutions/{slug}", response_model=InstitutionOut)
def update_institution(slug: str, body: InstitutionUpdate, _: PlatformAdmin, db: DbSession):
    return service.update(db, slug, body)


@router.post("/institutions/{slug}/admins", status_code=status.HTTP_201_CREATED, response_model=MemberOut)
def provision_admin(slug: str, body: ProvisionAdminRequest, _: PlatformAdmin, db: DbSession):
    membership = service.provision_college_admin(db, slug, body.email)
    return MemberOut(
        membership_id=membership.id,
        user_id=membership.user_id,
        full_name=membership.user.full_name,
        email=membership.user.email,
        role=membership.role,
        status=membership.status,
    )
