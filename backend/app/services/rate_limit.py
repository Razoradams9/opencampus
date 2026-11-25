"""Persistent, concurrency-safe rate limiting backed by PostgreSQL.

Algorithm: fixed windows. Each (policy, identity) pair maps to one row per
window, aligned to multiples of the window length in *database* time. A hit
is a single atomic upsert:

    INSERT ... ON CONFLICT (key_hash, window_start)
    DO UPDATE SET count = count + 1 RETURNING count

Concurrent hits on the same key serialise on the row, so no request can slip
past the limit. All policies for a request are checked in one statement.

Known limitation of fixed windows: a client can spend its full allowance at
the end of one window and again at the start of the next, i.e. up to 2x the
limit in a short burst across a boundary. Pairing a short window with a
longer one (5/min plus 20/hour) bounds the damage.

Every check runs in its own short transaction on its own connection and is
committed immediately, so counts survive even when the request that caused
them fails (a failed login rolls back the request transaction).

Keys are HMAC-SHA256(secret, policy + identity). Raw emails, IPs and session
ids are never stored, and keys cannot be linked to them without the secret.
"""

import hashlib
import hmac
import math
import random
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import bindparam, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError

from app.core.config import RateLimitPolicy, Settings
from app.core.errors import ApiError
from app.db.session import get_engine

# A small share of checks also purge expired rows, bounded per call.
_CLEANUP_PROBABILITY = 0.01
_CLEANUP_BATCH = 500

_HIT_SQL = """
WITH input(key_hash, seconds) AS (VALUES {rows}),
binned AS (
    SELECT key_hash,
           date_bin(make_interval(secs => seconds), now(), TIMESTAMPTZ '2000-01-01 00:00:00+00') AS window_start,
           seconds
    FROM input
)
INSERT INTO rate_limit_buckets (key_hash, window_start, count, expires_at)
SELECT key_hash, window_start, 1, window_start + make_interval(secs => seconds) FROM binned
ON CONFLICT (key_hash, window_start) DO UPDATE SET count = rate_limit_buckets.count + 1
RETURNING key_hash, count, expires_at, now() AS db_now
"""

_PEEK_SQL = text(
    "SELECT key_hash, count, expires_at, now() AS db_now FROM rate_limit_buckets "
    "WHERE key_hash IN :keys AND expires_at > now()"
).bindparams(bindparam("keys", expanding=True))

_CLEAR_SQL = text("DELETE FROM rate_limit_buckets WHERE key_hash IN :keys").bindparams(
    bindparam("keys", expanding=True)
)

_PURGE_SQL = text(
    "DELETE FROM rate_limit_buckets WHERE ctid IN "
    "(SELECT ctid FROM rate_limit_buckets WHERE expires_at <= now() LIMIT :batch)"
)


def rate_limited(retry_after: int) -> ApiError:
    # Same message for every bucket: reveals nothing about accounts or keys.
    return ApiError(
        429,
        "rate_limit_exceeded",
        "Too many attempts. Please wait and try again.",
        {"Retry-After": str(retry_after)},
    )


def unavailable() -> ApiError:
    return ApiError(
        503,
        "rate_limit_unavailable",
        "Sign-in is temporarily unavailable. Please try again shortly.",
        {"Retry-After": "30"},
    )


@dataclass(frozen=True)
class Bucket:
    policy: RateLimitPolicy
    key_hash: str


class RateLimiter:
    def __init__(self, secret: str, engine: Engine | None = None):
        self._secret = secret.encode()
        self._engine = engine

    @property
    def engine(self) -> Engine:
        return self._engine or get_engine()

    def buckets(self, policies: Sequence[RateLimitPolicy], identity: str) -> list[Bucket]:
        return [Bucket(p, self._key(p, identity)) for p in policies]

    def _key(self, policy: RateLimitPolicy, identity: str) -> str:
        message = f"{policy.name}\x1f{identity}".encode()
        return hmac.new(self._secret, message, hashlib.sha256).hexdigest()

    # ---- operations ---------------------------------------------------

    def hit(self, buckets: Sequence[Bucket], peek: Sequence[Bucket] = ()) -> None:
        """Count one event in `buckets`; also check (without counting) `peek`.
        Raises 429 if any bucket is over its limit, 503 if storage fails."""
        if not buckets and not peek:
            return
        rows = []
        try:
            with self.engine.begin() as conn:
                if buckets:
                    values = ", ".join(f"(:k{i}, CAST(:s{i} AS integer))" for i in range(len(buckets)))
                    params = {}
                    for i, bucket in enumerate(buckets):
                        params[f"k{i}"] = bucket.key_hash
                        params[f"s{i}"] = bucket.policy.window
                    rows += conn.execute(text(_HIT_SQL.format(rows=values)), params).all()
                if peek:
                    rows += conn.execute(_PEEK_SQL, {"keys": [b.key_hash for b in peek]}).all()
                if random.random() < _CLEANUP_PROBABILITY:
                    conn.execute(_PURGE_SQL, {"batch": _CLEANUP_BATCH})
        except SQLAlchemyError:
            raise unavailable() from None

        # A counted hit exceeds the limit once count > limit; a peeked bucket
        # blocks once it has already reached the limit.
        limits = {b.key_hash: (b.policy.limit, False) for b in buckets}
        limits.update({b.key_hash: (b.policy.limit, True) for b in peek})
        retry_after = 0
        for key_hash, count, expires_at, db_now in rows:
            limit, peeked = limits[key_hash]
            if count > limit or (peeked and count >= limit):
                retry_after = max(retry_after, _seconds_until(expires_at, db_now))
        if retry_after:
            raise rate_limited(retry_after)

    def clear(self, buckets: Sequence[Bucket]) -> None:
        if not buckets:
            return
        try:
            with self.engine.begin() as conn:
                conn.execute(_CLEAR_SQL, {"keys": [b.key_hash for b in buckets]})
        except SQLAlchemyError:
            raise unavailable() from None

    def purge_expired(self) -> int:
        """Delete all expired rows. For scheduled maintenance (CLI)."""
        total = 0
        with self.engine.begin() as conn:
            while True:
                deleted = conn.execute(_PURGE_SQL, {"batch": 5000}).rowcount
                total += deleted
                if deleted < 5000:
                    return total


def _seconds_until(expires_at: datetime, db_now: datetime) -> int:
    return max(1, math.ceil((expires_at - db_now).total_seconds()))


def get_rate_limiter(settings: Settings) -> RateLimiter:
    return RateLimiter(settings.rate_limit_secret)
