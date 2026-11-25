"""rate limit buckets

Revision ID: 0002
Revises: 0001
Create Date: 2026-11-25

Fixed-window counters for authentication rate limiting. Global security
infrastructure: no institution_id and no RLS (it holds no tenant data, only
HMAC keys and counts). The runtime role gets exactly the DML it needs.
"""

import os
import re
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _app_role() -> str:
    role = os.getenv("OPENCAMPUS_DB_APP_ROLE", "opencampus_app")
    if not re.fullmatch(r"[a-z_][a-z0-9_]{0,62}", role):
        raise ValueError(f"Invalid OPENCAMPUS_DB_APP_ROLE: {role!r}")
    return role


def upgrade() -> None:
    op.create_table(
        "rate_limit_buckets",
        sa.Column("key_hash", sa.String(length=64), nullable=False),
        sa.Column("window_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("count", sa.Integer(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("count > 0", name=op.f("ck_rate_limit_buckets_count_positive")),
        sa.CheckConstraint("expires_at > window_start", name=op.f("ck_rate_limit_buckets_window_order")),
        sa.PrimaryKeyConstraint("key_hash", "window_start", name="pk_rate_limit_buckets"),
    )
    op.create_index("ix_rate_limit_buckets_expires_at", "rate_limit_buckets", ["expires_at"])
    # INSERT/UPDATE: counting; SELECT: checking; DELETE: clearing and purging.
    op.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON rate_limit_buckets TO {_app_role()}")


def downgrade() -> None:
    op.drop_index("ix_rate_limit_buckets_expires_at", table_name="rate_limit_buckets")
    op.drop_table("rate_limit_buckets")
