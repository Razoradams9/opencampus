import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.models.enums import InstitutionStatus, MembershipRole, MembershipStatus

# Length-based policy (NIST SP 800-63B): no composition rules. The upper
# bound caps hashing cost for oversized inputs.
PASSWORD_MIN = 12
PASSWORD_MAX = 128


class StrictModel(BaseModel):
    # Unknown fields are rejected, so e.g. {"role": "college_admin"} in a
    # registration body fails validation instead of being silently ignored.
    model_config = ConfigDict(extra="forbid")


class RegisterRequest(StrictModel):
    email: EmailStr
    password: str = Field(min_length=PASSWORD_MIN, max_length=PASSWORD_MAX)
    full_name: str = Field(min_length=1, max_length=200)
    institution_slug: str = Field(min_length=1, max_length=63)

    @field_validator("full_name")
    @classmethod
    def strip_name(cls, value: str) -> str:
        value = " ".join(value.split())
        if not value:
            raise ValueError("Name is required")
        return value


class LoginRequest(StrictModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=PASSWORD_MAX)
    # Optional preference; honoured only if the user has an active membership there.
    institution_slug: str | None = Field(default=None, max_length=63)


class PasswordResetRequest(StrictModel):
    email: EmailStr


class PasswordResetConfirm(StrictModel):
    token: str = Field(min_length=20, max_length=200)
    new_password: str = Field(min_length=PASSWORD_MIN, max_length=PASSWORD_MAX)


class MessageResponse(BaseModel):
    message: str


class SwitchInstitutionRequest(StrictModel):
    institution_id: uuid.UUID


class UserOut(BaseModel):
    id: uuid.UUID
    email: str
    full_name: str
    is_platform_admin: bool


class InstitutionRef(BaseModel):
    id: uuid.UUID
    slug: str
    name: str
    status: InstitutionStatus


class MembershipOut(BaseModel):
    id: uuid.UUID
    role: MembershipRole
    status: MembershipStatus
    institution: InstitutionRef


class ActiveInstitution(InstitutionRef):
    role: MembershipRole


class MeResponse(BaseModel):
    user: UserOut
    active_institution: ActiveInstitution | None
    memberships: list[MembershipOut]


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    me: MeResponse


class SessionOut(BaseModel):
    id: uuid.UUID
    created_at: datetime
    last_seen_at: datetime
    user_agent: str | None
    current: bool
