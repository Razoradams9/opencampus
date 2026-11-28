import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, Enum, ForeignKeyConstraint, Index, String, Text, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin
from app.models.enums import PublicationStatus, ResourceType

publication_status = Enum(PublicationStatus, name="publication_status")


class LearningResource(TimestampMixin, Base):
    """Study material attached to a subject (M4.4). Tenant-owned: RLS.

    Content by type (enforced by ck_learning_resources_content):
      note                       -> body (text), no URL
      link, video, pdf, document,
      presentation               -> external_url (http/https) or storage_key
    storage_key is reserved for a future storage backend; no backend is
    configured, so the API never sets it and never exposes it.
    """

    __tablename__ = "learning_resources"
    __table_args__ = (
        # (subject, course) pair must exist together in the same institution.
        ForeignKeyConstraint(
            ["institution_id", "course_id", "subject_id"],
            ["subjects.institution_id", "subjects.course_id", "subjects.id"],
            name="fk_learning_resources_subject_in_course",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["institution_id", "created_by_membership_id"],
            ["memberships.institution_id", "memberships.id"],
            name="fk_learning_resources_author_same_institution",
            ondelete="RESTRICT",
        ),
        CheckConstraint(
            "(resource_type = 'note' AND body IS NOT NULL AND length(btrim(body)) > 0 AND external_url IS NULL)"
            " OR (resource_type <> 'note' AND (external_url IS NOT NULL OR storage_key IS NOT NULL))",
            name="content",
        ),
        CheckConstraint("external_url IS NULL OR external_url ~ '^https?://'", name="url_scheme"),
        CheckConstraint("status <> 'published' OR published_at IS NOT NULL", name="published_has_timestamp"),
        Index("ix_learning_resources_subject", "institution_id", "subject_id", "status"),
        Index("ix_learning_resources_course", "institution_id", "course_id", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    institution_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    course_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    subject_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    created_by_membership_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    resource_type: Mapped[ResourceType] = mapped_column(Enum(ResourceType, name="resource_type"), nullable=False)
    topic: Mapped[str | None] = mapped_column(String(120))
    body: Mapped[str | None] = mapped_column(Text)
    external_url: Mapped[str | None] = mapped_column(String(2048))
    storage_key: Mapped[str | None] = mapped_column(String(512))
    status: Mapped[PublicationStatus] = mapped_column(
        publication_status, nullable=False, server_default=PublicationStatus.draft.value
    )
    # First publication time; kept when archived. NULL if never published.
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
