import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, Enum, ForeignKeyConstraint, Index, String, Text, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin
from app.models.enums import AnnouncementAudience, AnnouncementPriority, PublicationStatus
from app.models.resource import publication_status


class Announcement(TimestampMixin, Base):
    """Academic announcement (M4.6). Tenant-owned: RLS.

    The audience columns are constrained together, and the references are
    tenant-aware composite FKs, so a row can only target a course/subject of
    its own institution and the (course, subject) pair is always consistent.
    """

    __tablename__ = "announcements"
    __table_args__ = (
        ForeignKeyConstraint(
            ["institution_id", "course_id"],
            ["courses.institution_id", "courses.id"],
            name="fk_announcements_course_same_institution",
            ondelete="RESTRICT",
        ),
        # MATCH SIMPLE: only checked when subject_id is set.
        ForeignKeyConstraint(
            ["institution_id", "course_id", "subject_id"],
            ["subjects.institution_id", "subjects.course_id", "subjects.id"],
            name="fk_announcements_subject_in_course",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["institution_id", "created_by_membership_id"],
            ["memberships.institution_id", "memberships.id"],
            name="fk_announcements_author_same_institution",
            ondelete="RESTRICT",
        ),
        CheckConstraint(
            "(audience = 'institution' AND course_id IS NULL AND subject_id IS NULL)"
            " OR (audience = 'course' AND course_id IS NOT NULL AND subject_id IS NULL)"
            " OR (audience IN ('subject', 'subject_students') AND course_id IS NOT NULL AND subject_id IS NOT NULL)",
            name="audience_target",
        ),
        CheckConstraint("status <> 'published' OR published_at IS NOT NULL", name="published_has_timestamp"),
        CheckConstraint("expires_at IS NULL OR published_at IS NULL OR expires_at > published_at", name="expires_after_publish"),
        Index("ix_announcements_feed", "institution_id", "status", "published_at"),
        Index("ix_announcements_subject", "institution_id", "subject_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    institution_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    created_by_membership_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    priority: Mapped[AnnouncementPriority] = mapped_column(
        Enum(AnnouncementPriority, name="announcement_priority"), nullable=False, server_default=AnnouncementPriority.normal.value
    )
    audience: Mapped[AnnouncementAudience] = mapped_column(Enum(AnnouncementAudience, name="announcement_audience"), nullable=False)
    course_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    subject_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    status: Mapped[PublicationStatus] = mapped_column(
        publication_status, nullable=False, server_default=PublicationStatus.draft.value
    )
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
