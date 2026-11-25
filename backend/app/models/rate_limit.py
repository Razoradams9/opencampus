from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, Index, Integer, String, PrimaryKeyConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class RateLimitBucket(Base):
    """One fixed-window counter. Global security infrastructure: not tenant-
    owned, no RLS. key_hash is an HMAC, never a raw email/IP/session id."""

    __tablename__ = "rate_limit_buckets"
    __table_args__ = (
        PrimaryKeyConstraint("key_hash", "window_start", name="pk_rate_limit_buckets"),
        CheckConstraint("count > 0", name="count_positive"),
        CheckConstraint("expires_at > window_start", name="window_order"),
        Index("ix_rate_limit_buckets_expires_at", "expires_at"),
    )

    key_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    window_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    count: Mapped[int] = mapped_column(Integer, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
