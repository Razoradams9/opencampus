"""Timetable (M4.3): rooms, faculty assignments and class sessions.

Integrity lives in the database where it can:
  * composite FKs keep every reference inside one institution and keep a
    session's course/subject/faculty identical to its assignment's;
  * GiST exclusion constraints make overlapping room or faculty bookings
    impossible, including under concurrent requests (no check-then-insert race).
"""

import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import UUID, ExcludeConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin
from app.models.course import academic_status
from app.models.enrolment import ACADEMIC_YEAR_PATTERN
from app.models.enums import AcademicStatus, AssignmentStatus, SessionStatus

MAX_SESSION_HOURS = 12


class Room(TimestampMixin, Base):
    __tablename__ = "rooms"
    __table_args__ = (
        UniqueConstraint("institution_id", "building", "name", name="uq_rooms_institution_building_name"),
        UniqueConstraint("institution_id", "id", name="uq_rooms_institution_id"),
        CheckConstraint("capacity IS NULL OR capacity > 0", name="capacity_positive"),
        ForeignKeyConstraint(["institution_id"], ["institutions.id"], name="fk_rooms_institution", ondelete="RESTRICT"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    institution_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    building: Mapped[str] = mapped_column(String(100), nullable=False, server_default="")
    capacity: Mapped[int | None] = mapped_column(Integer)
    status: Mapped[AcademicStatus] = mapped_column(academic_status, nullable=False, server_default=AcademicStatus.active.value)


class FacultyAssignment(TimestampMixin, Base):
    """Explicitly makes a faculty member responsible for a subject (in its
    course) for one academic year and period. It is also the grant that lets
    that faculty member see the matching enrolments."""

    __tablename__ = "faculty_assignments"
    __table_args__ = (
        ForeignKeyConstraint(
            ["institution_id", "course_id", "subject_id"],
            ["subjects.institution_id", "subjects.course_id", "subjects.id"],
            name="fk_faculty_assignments_subject_in_course",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["institution_id", "faculty_membership_id"],
            ["memberships.institution_id", "memberships.id"],
            name="fk_faculty_assignments_membership_same_institution",
            ondelete="RESTRICT",
        ),
        # FK target for class_sessions: pins faculty, course and subject.
        UniqueConstraint(
            "institution_id", "id", "faculty_membership_id", "course_id", "subject_id",
            name="uq_faculty_assignments_session_target",
        ),
        Index(
            "uq_faculty_assignments_active",
            "institution_id", "subject_id", "faculty_membership_id", "academic_year", "academic_period",
            unique=True,
            postgresql_where=text("status = 'active'"),
        ),
        Index("ix_faculty_assignments_faculty", "institution_id", "faculty_membership_id"),
        Index("ix_faculty_assignments_course_period", "institution_id", "course_id", "academic_year", "academic_period"),
        CheckConstraint(f"academic_year ~ '{ACADEMIC_YEAR_PATTERN}'", name="academic_year_format"),
        CheckConstraint("length(btrim(academic_period)) > 0", name="academic_period_present"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    institution_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    course_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    subject_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    faculty_membership_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    academic_year: Mapped[str] = mapped_column(String(7), nullable=False)
    academic_period: Mapped[str] = mapped_column(String(40), nullable=False)
    status: Mapped[AssignmentStatus] = mapped_column(
        Enum(AssignmentStatus, name="assignment_status"), nullable=False, server_default=AssignmentStatus.active.value
    )


class ClassSession(TimestampMixin, Base):
    """One scheduled class with explicit start and end (no recurrence engine).

    course_id, subject_id and faculty_membership_id are copies of the
    assignment's values, enforced by the composite FK; the copy is what lets
    the faculty exclusion constraint work without a join.
    """

    __tablename__ = "class_sessions"
    __table_args__ = (
        ForeignKeyConstraint(
            ["institution_id", "faculty_assignment_id", "faculty_membership_id", "course_id", "subject_id"],
            [
                "faculty_assignments.institution_id",
                "faculty_assignments.id",
                "faculty_assignments.faculty_membership_id",
                "faculty_assignments.course_id",
                "faculty_assignments.subject_id",
            ],
            name="fk_class_sessions_assignment_consistent",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["institution_id", "room_id"],
            ["rooms.institution_id", "rooms.id"],
            name="fk_class_sessions_room_same_institution",
            ondelete="RESTRICT",
        ),
        CheckConstraint("end_at > start_at", name="ends_after_start"),
        CheckConstraint(f"end_at - start_at <= interval '{MAX_SESSION_HOURS} hours'", name="max_duration"),
        ExcludeConstraint(
            ("institution_id", "="),
            ("room_id", "="),
            (text("tstzrange(start_at, end_at, '[)')"), "&&"),
            name="ex_class_sessions_room_overlap",
            using="gist",
            where=text("status = 'scheduled' AND room_id IS NOT NULL"),
        ),
        ExcludeConstraint(
            ("institution_id", "="),
            ("faculty_membership_id", "="),
            (text("tstzrange(start_at, end_at, '[)')"), "&&"),
            name="ex_class_sessions_faculty_overlap",
            using="gist",
            where=text("status = 'scheduled'"),
        ),
        Index("ix_class_sessions_start", "institution_id", "start_at"),
        Index("ix_class_sessions_course", "institution_id", "course_id", "start_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    institution_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    faculty_assignment_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    faculty_membership_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    course_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    subject_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    room_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    start_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    end_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[SessionStatus] = mapped_column(
        Enum(SessionStatus, name="session_status"), nullable=False, server_default=SessionStatus.scheduled.value
    )
