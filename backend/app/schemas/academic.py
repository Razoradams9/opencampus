"""Request/response schemas for /api/academic.

institution_id never appears in a request schema: the tenant always comes
from the server-side session. Identifiers of other tenant-owned records
(course_id, membership ids, ...) are accepted but re-validated against the
tenant by the service layer.
"""

import re
import uuid
from datetime import datetime
from decimal import Decimal
from typing import Annotated, ClassVar

from pydantic import AfterValidator, BaseModel, Field, model_validator

from app.models.course import CODE_PATTERN
from app.models.enums import AcademicStatus, DegreeLevel
from app.schemas.auth import StrictModel


def _clean_text(value: str) -> str:
    value = " ".join(value.split())
    if not value:
        raise ValueError("must not be blank")
    return value


def _clean_code(value: str) -> str:
    value = value.strip().upper()
    if not re.fullmatch(CODE_PATTERN, value):
        raise ValueError("use letters, digits, '.', '_' or '-' (max 32), starting with a letter or digit")
    return value


Name = Annotated[str, Field(min_length=1, max_length=200), AfterValidator(_clean_text)]
Code = Annotated[str, Field(min_length=1, max_length=40), AfterValidator(_clean_code)]
Description = Annotated[str | None, Field(default=None, max_length=4000)]
Credits = Annotated[Decimal, Field(gt=0, le=99, max_digits=3, decimal_places=1)]


class PatchModel(StrictModel):
    """PATCH bodies: omitted fields are untouched; explicit null is only
    accepted for fields listed in NULLABLE."""

    NULLABLE: ClassVar[frozenset[str]] = frozenset()

    @model_validator(mode="after")
    def _no_null_for_required(self):
        for name in self.model_fields_set:
            if getattr(self, name) is None and name not in self.NULLABLE:
                raise ValueError(f"{name} cannot be null")
        return self

    def changes(self) -> dict:
        return {name: getattr(self, name) for name in self.model_fields_set}


# ---- Courses ---------------------------------------------------------------


class CourseCreate(StrictModel):
    name: Name
    code: Code
    description: Description = None
    degree_level: DegreeLevel
    duration_semesters: int = Field(ge=1, le=20)


class CourseUpdate(PatchModel):
    NULLABLE = frozenset({"description"})

    name: Name | None = None
    code: Code | None = None
    description: Description = None
    degree_level: DegreeLevel | None = None
    duration_semesters: int | None = Field(default=None, ge=1, le=20)


class CourseOut(BaseModel):
    id: uuid.UUID
    name: str
    code: str
    description: str | None
    degree_level: DegreeLevel
    duration_semesters: int
    status: AcademicStatus
    created_at: datetime
    updated_at: datetime


class CourseRef(BaseModel):
    id: uuid.UUID
    name: str
    code: str
    status: AcademicStatus


# ---- Subjects --------------------------------------------------------------


class SubjectCreate(StrictModel):
    name: Name
    code: Code
    description: Description = None
    semester: int = Field(ge=1, le=20)
    credits: Credits


class SubjectUpdate(PatchModel):
    NULLABLE = frozenset({"description"})

    name: Name | None = None
    code: Code | None = None
    description: Description = None
    semester: int | None = Field(default=None, ge=1, le=20)
    credits: Credits | None = None


class SubjectOut(BaseModel):
    id: uuid.UUID
    course_id: uuid.UUID
    name: str
    code: str
    description: str | None
    semester: int
    credits: float
    status: AcademicStatus
    created_at: datetime
    updated_at: datetime
