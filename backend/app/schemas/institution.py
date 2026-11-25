import uuid
from typing import Literal

from pydantic import BaseModel, EmailStr, Field

from app.models.enums import InstitutionStatus, MembershipRole, MembershipStatus
from app.schemas.auth import StrictModel

SLUG_PATTERN = r"^[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?$"


class InstitutionPublic(BaseModel):
    slug: str
    name: str
    status: InstitutionStatus
    registration_open: bool


class InstitutionOut(BaseModel):
    id: uuid.UUID
    slug: str
    name: str
    status: InstitutionStatus
    allow_self_registration: bool


class InstitutionCreate(StrictModel):
    slug: str = Field(pattern=SLUG_PATTERN)
    name: str = Field(min_length=2, max_length=200)
    allow_self_registration: bool = False


class InstitutionUpdate(StrictModel):
    status: InstitutionStatus | None = None
    allow_self_registration: bool | None = None


class ProvisionAdminRequest(StrictModel):
    email: EmailStr


class CurrentInstitution(BaseModel):
    institution: InstitutionOut
    role: MembershipRole


class MemberOut(BaseModel):
    membership_id: uuid.UUID
    user_id: uuid.UUID
    full_name: str
    email: str
    role: MembershipRole
    status: MembershipStatus


class MemberUpdate(StrictModel):
    # College admins can move members between student and faculty, or
    # suspend them. Granting college_admin is platform-provisioned only.
    role: Literal["student", "faculty"] | None = None
    status: MembershipStatus | None = None
