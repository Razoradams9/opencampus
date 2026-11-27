import uuid

from sqlalchemy import Boolean, CheckConstraint, Enum, String, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin
from app.models.enums import InstitutionStatus


class Institution(TimestampMixin, Base):
    """A college/tenant. Global registry: not itself tenant-owned."""

    __tablename__ = "institutions"
    __table_args__ = (
        CheckConstraint(r"slug ~ '^[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?$'", name="slug_format"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    slug: Mapped[str] = mapped_column(String(63), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    status: Mapped[InstitutionStatus] = mapped_column(
        Enum(InstitutionStatus, name="institution_status"), nullable=False, server_default=InstitutionStatus.active.value
    )
    # Off by default: an institution must opt in to public student sign-up.
    allow_self_registration: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    # IANA zone (e.g. "Asia/Kolkata") used to interpret timetable weeks.
    # Timestamps are always stored in UTC; this only affects day/week boundaries.
    timezone: Mapped[str] = mapped_column(String(64), nullable=False, server_default="UTC")

    memberships: Mapped[list["Membership"]] = relationship(back_populates="institution")  # noqa: F821
