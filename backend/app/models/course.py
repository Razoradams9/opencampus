import uuid
from decimal import Decimal

from sqlalchemy import CheckConstraint, Enum, ForeignKey, ForeignKeyConstraint, Integer, Numeric, String, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin
from app.models.enums import AcademicStatus, DegreeLevel

# Codes are stored upper-case so uniqueness is case-insensitive in effect.
CODE_PATTERN = r"^[A-Z0-9][A-Z0-9._-]{0,31}$"

academic_status = Enum(AcademicStatus, name="academic_status")


class Course(TimestampMixin, Base):
    """A programme of study (e.g. B.Sc. Computer Science). Tenant-owned: RLS."""

    __tablename__ = "courses"
    __table_args__ = (
        UniqueConstraint("institution_id", "code", name="uq_courses_institution_code"),
        # Target for composite (tenant-aware) foreign keys from child tables.
        UniqueConstraint("institution_id", "id", name="uq_courses_institution_id"),
        CheckConstraint("duration_semesters BETWEEN 1 AND 20", name="duration_range"),
        CheckConstraint(f"code ~ '{CODE_PATTERN}'", name="code_format"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    institution_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("institutions.id", ondelete="RESTRICT"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    code: Mapped[str] = mapped_column(String(32), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    degree_level: Mapped[DegreeLevel] = mapped_column(Enum(DegreeLevel, name="degree_level"), nullable=False)
    duration_semesters: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[AcademicStatus] = mapped_column(
        academic_status, nullable=False, server_default=AcademicStatus.active.value
    )


class Subject(TimestampMixin, Base):
    """A unit taught within one course, in one semester of it. Tenant-owned: RLS."""

    __tablename__ = "subjects"
    __table_args__ = (
        # Codes are unique within a course; two courses may reuse a code.
        UniqueConstraint("institution_id", "course_id", "code", name="uq_subjects_course_code"),
        UniqueConstraint("institution_id", "id", name="uq_subjects_institution_id"),
        # FK target that also pins the course: (subject, course) pairs are
        # always consistent for rows that reference it (M4.3).
        UniqueConstraint("institution_id", "course_id", "id", name="uq_subjects_institution_course_id"),
        # Composite FK: the course must belong to the same institution.
        ForeignKeyConstraint(
            ["institution_id", "course_id"],
            ["courses.institution_id", "courses.id"],
            name="fk_subjects_course_same_institution",
            ondelete="RESTRICT",
        ),
        CheckConstraint("semester >= 1", name="semester_positive"),
        CheckConstraint("credits > 0", name="credits_positive"),
        CheckConstraint(f"code ~ '{CODE_PATTERN}'", name="code_format"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    institution_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    course_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    code: Mapped[str] = mapped_column(String(32), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    # Upper bound (<= course.duration_semesters) is checked by the service
    # under a row lock on the course; it spans two tables.
    semester: Mapped[int] = mapped_column(Integer, nullable=False)
    credits: Mapped[Decimal] = mapped_column(Numeric(4, 1), nullable=False)
    status: Mapped[AcademicStatus] = mapped_column(
        academic_status, nullable=False, server_default=AcademicStatus.active.value
    )
