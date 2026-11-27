import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, Enum, ForeignKeyConstraint, Index, String, func, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin
from app.models.enums import EnrolmentStatus

ACADEMIC_YEAR_PATTERN = r"^[0-9]{4}-[0-9]{2}$"  # e.g. 2026-27
OPEN_STATUSES = ("active", "suspended")


class Enrolment(TimestampMixin, Base):
    """A student's enrolment in a course for one academic year and period.

    The student is referenced by *membership*, not user: identity stays in
    users, and the composite FK guarantees the membership belongs to the same
    institution as the enrolment (and the course). Rows are never deleted;
    withdrawal and completion are status changes. Tenant-owned: RLS.
    """

    __tablename__ = "enrolments"
    __table_args__ = (
        ForeignKeyConstraint(
            ["institution_id", "student_membership_id"],
            ["memberships.institution_id", "memberships.id"],
            name="fk_enrolments_membership_same_institution",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["institution_id", "course_id"],
            ["courses.institution_id", "courses.id"],
            name="fk_enrolments_course_same_institution",
            ondelete="RESTRICT",
        ),
        # At most one open (active or suspended) enrolment per student, course
        # and academic period. Closed rows are history and may repeat.
        Index(
            "uq_enrolments_open",
            "institution_id",
            "student_membership_id",
            "course_id",
            "academic_year",
            "academic_period",
            unique=True,
            postgresql_where=text("status IN ('active', 'suspended')"),
        ),
        Index("ix_enrolments_course", "institution_id", "course_id", "academic_year", "academic_period"),
        CheckConstraint(f"academic_year ~ '{ACADEMIC_YEAR_PATTERN}'", name="academic_year_format"),
        CheckConstraint("length(btrim(academic_period)) > 0", name="academic_period_present"),
        CheckConstraint("(status = 'completed') = (completed_at IS NOT NULL)", name="completed_at_matches_status"),
        CheckConstraint("(status = 'withdrawn') = (withdrawn_at IS NOT NULL)", name="withdrawn_at_matches_status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    institution_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    student_membership_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    course_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    academic_year: Mapped[str] = mapped_column(String(7), nullable=False)
    academic_period: Mapped[str] = mapped_column(String(40), nullable=False)
    status: Mapped[EnrolmentStatus] = mapped_column(
        Enum(EnrolmentStatus, name="enrolment_status"), nullable=False, server_default=EnrolmentStatus.active.value
    )
    enrolled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    withdrawn_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
