"""Request/response schemas for /api/academic.

institution_id never appears in a request schema: the tenant always comes
from the server-side session. Identifiers of other tenant-owned records
(course_id, membership ids, ...) are accepted but re-validated against the
tenant by the service layer.
"""

import re
import uuid
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Annotated, ClassVar

from pydantic import AfterValidator, AwareDatetime, BaseModel, Field, PlainSerializer, model_validator

from app.models.course import CODE_PATTERN
from app.models.enums import (
    AcademicStatus,
    AssignmentStatus,
    DegreeLevel,
    EnrolmentStatus,
    LatePolicy,
    PublicationStatus,
    ResourceType,
    SessionStatus,
)
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


# ---- Enrolments (M4.2) -----------------------------------------------------


def _check_academic_year(value: str) -> str:
    value = value.strip()
    match = re.fullmatch(r"(\d{4})-(\d{2})", value)
    if not match or (int(match[1]) + 1) % 100 != int(match[2]):
        raise ValueError("use the form 2026-27 (consecutive years)")
    return value


AcademicYear = Annotated[str, Field(min_length=7, max_length=7), AfterValidator(_check_academic_year)]
AcademicPeriod = Annotated[str, Field(min_length=1, max_length=40), AfterValidator(_clean_text)]


class EnrolmentCreate(StrictModel):
    student_membership_id: uuid.UUID
    course_id: uuid.UUID
    academic_year: AcademicYear
    academic_period: AcademicPeriod


class EnrolmentUpdate(StrictModel):
    # Course, student and period are fixed: a different one is a new enrolment,
    # so history stays truthful. Timestamps are set by the server.
    status: EnrolmentStatus


class PersonRef(BaseModel):
    membership_id: uuid.UUID
    user_id: uuid.UUID
    full_name: str
    email: str


class EnrolmentOut(BaseModel):
    id: uuid.UUID
    student: PersonRef
    course: CourseRef
    academic_year: str
    academic_period: str
    status: EnrolmentStatus
    enrolled_at: datetime
    completed_at: datetime | None
    withdrawn_at: datetime | None
    created_at: datetime
    updated_at: datetime


# ---- Timetable (M4.3) ------------------------------------------------------


class RoomCreate(StrictModel):
    name: Annotated[str, Field(min_length=1, max_length=100), AfterValidator(_clean_text)]
    building: Annotated[str, Field(max_length=100)] = ""
    capacity: int | None = Field(default=None, ge=1, le=100_000)

    @model_validator(mode="after")
    def _tidy_building(self):
        self.building = " ".join(self.building.split())
        return self


class RoomUpdate(PatchModel):
    NULLABLE = frozenset({"capacity"})

    name: Annotated[str, Field(min_length=1, max_length=100), AfterValidator(_clean_text)] | None = None
    building: Annotated[str, Field(max_length=100)] | None = None
    capacity: int | None = Field(default=None, ge=1, le=100_000)

    @model_validator(mode="after")
    def _tidy_building(self):
        if self.building is not None:
            self.building = " ".join(self.building.split())
        return self


class RoomOut(BaseModel):
    id: uuid.UUID
    name: str
    building: str
    capacity: int | None
    status: AcademicStatus


class RoomRef(BaseModel):
    id: uuid.UUID
    name: str
    building: str


class AssignmentCreate(StrictModel):
    # The course is derived from the subject, so the pair is always consistent.
    subject_id: uuid.UUID
    faculty_membership_id: uuid.UUID
    academic_year: AcademicYear
    academic_period: AcademicPeriod


class SubjectRef(BaseModel):
    id: uuid.UUID
    name: str
    code: str
    semester: int
    credits: float


class TeacherRef(BaseModel):
    # Deliberately no email: students see who teaches, not contact data.
    membership_id: uuid.UUID
    full_name: str


class AssignmentOut(BaseModel):
    id: uuid.UUID
    course: CourseRef
    subject: SubjectRef
    faculty: TeacherRef
    academic_year: str
    academic_period: str
    status: AssignmentStatus
    created_at: datetime
    updated_at: datetime


def _to_utc(value: datetime) -> datetime:
    return value.astimezone(timezone.utc)


# Offset-aware only (a naive "09:00" is ambiguous across timezones); stored
# and returned in UTC whatever offset the client used.
UtcDatetime = Annotated[AwareDatetime, AfterValidator(_to_utc)]
UtcOut = Annotated[datetime, PlainSerializer(lambda v: _to_utc(v).isoformat().replace("+00:00", "Z"), return_type=str)]


class SessionCreate(StrictModel):
    # course, subject and faculty come from the assignment, never the client.
    faculty_assignment_id: uuid.UUID
    room_id: uuid.UUID | None = None
    start_at: UtcDatetime
    end_at: UtcDatetime


class SessionUpdate(PatchModel):
    NULLABLE = frozenset({"room_id"})

    faculty_assignment_id: uuid.UUID | None = None
    room_id: uuid.UUID | None = None
    start_at: UtcDatetime | None = None
    end_at: UtcDatetime | None = None


class SessionOut(BaseModel):
    id: uuid.UUID
    start_at: UtcOut
    end_at: UtcOut
    status: SessionStatus
    course: CourseRef
    subject: SubjectRef
    faculty: TeacherRef
    room: RoomRef | None
    faculty_assignment_id: uuid.UUID
    academic_year: str
    academic_period: str
    created_at: datetime
    updated_at: datetime


class TimetableWeek(BaseModel):
    timezone: str  # IANA zone the week boundaries were computed in
    week_start: date  # Monday, in that timezone
    week_end: date  # following Monday (exclusive)
    starts_at: datetime
    ends_at: datetime
    sessions: list[SessionOut]


# ---- Learning resources (M4.4) ---------------------------------------------


def _check_url(value: str) -> str:
    """http(s) URLs with a host only: rejects javascript:, data:, file: etc."""
    from urllib.parse import urlsplit

    value = value.strip()
    parts = urlsplit(value)
    if parts.scheme.lower() not in ("http", "https") or not parts.hostname or any(c.isspace() for c in value):
        raise ValueError("enter a full http:// or https:// address")
    return value


HttpUrlText = Annotated[str, Field(min_length=8, max_length=2048), AfterValidator(_check_url)]
Title = Annotated[str, Field(min_length=1, max_length=200), AfterValidator(_clean_text)]
Topic = Annotated[str, Field(min_length=1, max_length=120), AfterValidator(_clean_text)]
LongText = Annotated[str, Field(min_length=1, max_length=50_000)]


def check_resource_content(resource_type: ResourceType, body: str | None, external_url: str | None) -> None:
    """Shared by create and update (where it runs on the merged result)."""
    if resource_type == ResourceType.note:
        if not body or not body.strip():
            raise ValueError("a text note needs content")
        if external_url:
            raise ValueError("a text note cannot have a link")
    elif not external_url:
        # No file storage is configured yet: files are referenced by URL.
        raise ValueError(f"a {resource_type.value} resource needs a link (file uploads are not available yet)")


class ResourceCreate(StrictModel):
    title: Title
    description: Description = None
    resource_type: ResourceType
    topic: Topic | None = None
    body: LongText | None = None
    external_url: HttpUrlText | None = None

    @model_validator(mode="after")
    def _content(self):
        check_resource_content(self.resource_type, self.body, self.external_url)
        return self


class ResourceUpdate(PatchModel):
    NULLABLE = frozenset({"description", "topic", "body", "external_url"})

    title: Title | None = None
    description: Description = None
    resource_type: ResourceType | None = None
    topic: Topic | None = None
    body: LongText | None = None
    external_url: HttpUrlText | None = None


class ResourceOut(BaseModel):
    id: uuid.UUID
    course: CourseRef
    subject: SubjectRef
    title: str
    description: str | None
    resource_type: ResourceType
    topic: str | None
    body: str | None
    external_url: str | None
    file_available: bool  # always false until a storage provider exists
    status: PublicationStatus
    created_by: TeacherRef
    published_at: datetime | None
    created_at: datetime
    updated_at: datetime


# ---- Assignments and submissions (M4.5) ------------------------------------

Marks = Annotated[Decimal, Field(ge=0, le=1000, max_digits=6, decimal_places=2)]
MaxMarks = Annotated[Decimal, Field(gt=0, le=1000, max_digits=6, decimal_places=2)]


def check_assignment_dates(available_from: datetime, due_at: datetime, late_policy: LatePolicy, late_cutoff_at: datetime | None) -> None:
    if due_at <= available_from:
        raise ValueError("the deadline must be after the available-from time")
    if late_policy == LatePolicy.accept_until:
        if late_cutoff_at is None:
            raise ValueError("set a final cut-off for late submissions")
        if late_cutoff_at <= due_at:
            raise ValueError("the late cut-off must be after the deadline")
    elif late_cutoff_at is not None:
        raise ValueError("a late cut-off only applies to the 'accept until' policy")


class AssignmentWorkCreate(StrictModel):
    title: Title
    instructions: LongText
    reference_url: HttpUrlText | None = None
    available_from: UtcDatetime
    due_at: UtcDatetime
    late_policy: LatePolicy = LatePolicy.reject
    late_cutoff_at: UtcDatetime | None = None
    max_marks: MaxMarks

    @model_validator(mode="after")
    def _dates(self):
        check_assignment_dates(self.available_from, self.due_at, self.late_policy, self.late_cutoff_at)
        return self


class AssignmentWorkUpdate(PatchModel):
    NULLABLE = frozenset({"reference_url", "late_cutoff_at"})

    title: Title | None = None
    instructions: LongText | None = None
    reference_url: HttpUrlText | None = None
    available_from: UtcDatetime | None = None
    due_at: UtcDatetime | None = None
    late_policy: LatePolicy | None = None
    late_cutoff_at: UtcDatetime | None = None
    max_marks: MaxMarks | None = None


class GradeOut(BaseModel):
    marks_awarded: float
    feedback: str | None
    graded_at: UtcOut
    graded_by: TeacherRef


class StudentProgress(BaseModel):
    """The calling student's own state for an assignment."""

    status: str  # not_submitted | submitted | graded
    attempts: int
    last_submitted_at: UtcOut | None
    is_late: bool
    grade: GradeOut | None


class AssignmentWorkOut(BaseModel):
    id: uuid.UUID
    course: CourseRef
    subject: SubjectRef
    title: str
    instructions: str
    reference_url: str | None
    available_from: UtcOut
    due_at: UtcOut
    late_policy: LatePolicy
    late_cutoff_at: UtcOut | None
    max_marks: float
    status: PublicationStatus
    published_at: UtcOut | None
    created_by: TeacherRef
    # Server's view of the window right now: not_open | open | late | closed.
    window: str
    me: StudentProgress | None = None  # students only
    submitted_students: int | None = None  # managers only
    graded_students: int | None = None  # managers only
    created_at: datetime
    updated_at: datetime


class SubmissionCreate(StrictModel):
    body: LongText

    @model_validator(mode="after")
    def _not_blank(self):
        if not self.body.strip():
            raise ValueError("the submission is empty")
        return self


class GradeCreate(StrictModel):
    marks_awarded: Marks
    feedback: Annotated[str | None, Field(default=None, max_length=20_000)] = None


class SubmissionOut(BaseModel):
    id: uuid.UUID
    assignment_id: uuid.UUID
    student: PersonRef
    attempt: int
    body: str | None
    file_available: bool
    submitted_at: UtcOut
    is_late: bool
    status: str  # submitted | graded | superseded (a later attempt exists)
    grade: GradeOut | None  # current (latest) grade
    grade_history: list[GradeOut]  # oldest first; includes the current one
