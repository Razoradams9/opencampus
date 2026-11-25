import uuid

from sqlalchemy import Enum, ForeignKey, Index, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin
from app.models.enums import MembershipRole, MembershipStatus


class Membership(TimestampMixin, Base):
    """A user's role within one institution. Tenant-owned: protected by RLS."""

    __tablename__ = "memberships"
    __table_args__ = (
        UniqueConstraint("institution_id", "user_id", name="uq_memberships_institution_user"),
        Index("ix_memberships_user_id", "user_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    institution_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("institutions.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    role: Mapped[MembershipRole] = mapped_column(
        Enum(MembershipRole, name="membership_role"), nullable=False, server_default=MembershipRole.student.value
    )
    status: Mapped[MembershipStatus] = mapped_column(
        Enum(MembershipStatus, name="membership_status"), nullable=False, server_default=MembershipStatus.active.value
    )

    institution: Mapped["Institution"] = relationship(back_populates="memberships", lazy="joined")  # noqa: F821
    user: Mapped["User"] = relationship(back_populates="memberships")  # noqa: F821
