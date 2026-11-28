"""Assignments and submissions (M4.5).

Submissions and grades are append-only: the runtime role may INSERT and
SELECT them but never UPDATE or DELETE, so a resubmission or a regrade adds a
row and history cannot be rewritten, even by a faulty service.
"""

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKeyConstraint,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin
from app.models.enums import LatePolicy, PublicationStatus
from app.models.resource import publication_status


class Assignment(TimestampMixin, Base):
    """Coursework set for a subject (not to be confused with FacultyAssignment)."""

    __tablename__ = "assignments"
    __table_args__ = (
        ForeignKeyConstraint(
            ["institution_id", "course_id", "subject_id"],
            ["subjects.institution_id", "subjects.course_id", "subjects.id"],
            name="fk_assignments_subject_in_course",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["institution_id", "created_by_membership_id"],
            ["memberships.institution_id", "memberships.id"],
            name="fk_assignments_author_same_institution",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("institution_id", "id", name="uq_assignments_institution_id"),
        CheckConstraint("due_at > available_from", name="due_after_available"),
        CheckConstraint("max_marks > 0 AND max_marks <= 1000", name="max_marks_range"),
        CheckConstraint("(late_policy = 'accept_until') = (late_cutoff_at IS NOT NULL)", name="cutoff_matches_policy"),
        CheckConstraint("late_cutoff_at IS NULL OR late_cutoff_at > due_at", name="cutoff_after_due"),
        CheckConstraint("reference_url IS NULL OR reference_url ~ '^https?://'", name="url_scheme"),
        CheckConstraint("status <> 'published' OR published_at IS NOT NULL", name="published_has_timestamp"),
        Index("ix_assignments_subject", "institution_id", "subject_id", "status"),
        Index("ix_assignments_course_due", "institution_id", "course_id", "due_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    institution_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    course_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    subject_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    created_by_membership_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    instructions: Mapped[str] = mapped_column(Text, nullable=False)
    reference_url: Mapped[str | None] = mapped_column(String(2048))
    available_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    due_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    late_policy: Mapped[LatePolicy] = mapped_column(
        Enum(LatePolicy, name="late_policy"), nullable=False, server_default=LatePolicy.reject.value
    )
    late_cutoff_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    max_marks: Mapped[Decimal] = mapped_column(Numeric(6, 2), nullable=False)
    status: Mapped[PublicationStatus] = mapped_column(
        publication_status, nullable=False, server_default=PublicationStatus.draft.value
    )
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Submission(Base):
    """One attempt by one student. Immutable once written (no UPDATE grant)."""

    __tablename__ = "submissions"
    __table_args__ = (
        ForeignKeyConstraint(
            ["institution_id", "assignment_id"],
            ["assignments.institution_id", "assignments.id"],
            name="fk_submissions_assignment_same_institution",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["institution_id", "student_membership_id"],
            ["memberships.institution_id", "memberships.id"],
            name="fk_submissions_student_same_institution",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("institution_id", "id", name="uq_submissions_institution_id"),
        # Attempts are numbered per student and assignment; a concurrent
        # duplicate attempt number fails here instead of overwriting.
        UniqueConstraint(
            "institution_id", "assignment_id", "student_membership_id", "attempt", name="uq_submissions_attempt"
        ),
        CheckConstraint("attempt >= 1", name="attempt_positive"),
        CheckConstraint("(body IS NOT NULL AND length(btrim(body)) > 0) OR storage_key IS NOT NULL", name="has_content"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    institution_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    assignment_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    student_membership_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    attempt: Mapped[int] = mapped_column(Integer, nullable=False)
    body: Mapped[str | None] = mapped_column(Text)
    storage_key: Mapped[str | None] = mapped_column(String(512))  # reserved: no storage provider yet
    submitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    # Decided by the server at submission time from the assignment's policy;
    # later deadline edits do not rewrite it.
    is_late: Mapped[bool] = mapped_column(Boolean, nullable=False)


class SubmissionGrade(Base):
    """A grading event. The newest row is the current grade; earlier rows are
    the regrading history. Immutable once written."""

    __tablename__ = "submission_grades"
    __table_args__ = (
        ForeignKeyConstraint(
            ["institution_id", "submission_id"],
            ["submissions.institution_id", "submissions.id"],
            name="fk_submission_grades_submission_same_institution",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["institution_id", "graded_by_membership_id"],
            ["memberships.institution_id", "memberships.id"],
            name="fk_submission_grades_grader_same_institution",
            ondelete="RESTRICT",
        ),
        CheckConstraint("marks_awarded >= 0", name="marks_non_negative"),
        Index("ix_submission_grades_submission", "institution_id", "submission_id", "graded_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    institution_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    submission_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    graded_by_membership_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    marks_awarded: Mapped[Decimal] = mapped_column(Numeric(6, 2), nullable=False)
    feedback: Mapped[str | None] = mapped_column(Text)
    graded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
