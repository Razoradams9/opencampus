import uuid
from typing import Annotated, Literal

from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import AfterValidator, BaseModel, EmailStr, Field

from app.models.enums import InstitutionStatus, MembershipRole, MembershipStatus
from app.schemas.auth import StrictModel

SLUG_PATTERN = r"^[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?$"


def _check_timezone(value: str) -> str:
    value = value.strip()
    try:
        ZoneInfo(value)
    except (ZoneInfoNotFoundError, ValueError):
        raise ValueError("use an IANA timezone name such as Asia/Kolkata or Europe/London") from None
    return value


TimezoneName = Annotated[str, Field(min_length=1, max_length=64), AfterValidator(_check_timezone)]


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
    timezone: str


class InstitutionCreate(StrictModel):
    slug: str = Field(pattern=SLUG_PATTERN)
    name: str = Field(min_length=2, max_length=200)
    allow_self_registration: bool = False
    timezone: TimezoneName = "UTC"


class InstitutionUpdate(StrictModel):
    status: InstitutionStatus | None = None
    allow_self_registration: bool | None = None
    timezone: TimezoneName | None = None


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
