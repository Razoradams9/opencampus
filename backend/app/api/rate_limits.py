"""Rate-limit guards for the authentication endpoints.

Kept separate from the auth service so the service stays about identity, and
so each guard runs *before* the expensive or state-changing work it protects.
"""

from fastapi import Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.client_ip import client_ip
from app.core.config import Settings
from app.core.security import hash_refresh_token
from app.models import RefreshToken
from app.services.auth import normalise_email
from app.services.rate_limit import Bucket, get_rate_limiter


def _ip(request: Request, settings: Settings) -> str:
    return client_ip(request, settings.trusted_proxies)


class LoginGuard:
    """IP limits on every attempt; per-account limits on *failed* attempts.

    The account identity is the normalised email whether or not an account
    exists, and the 429 is identical either way, so limits never reveal
    whether an email is registered."""

    def __init__(self, request: Request, settings: Settings, email: str):
        self._limiter = get_rate_limiter(settings)
        self._ip_buckets = self._limiter.buckets(settings.rl_login_ip, _ip(request, settings))
        self._account_buckets = self._limiter.buckets(settings.rl_login_account, normalise_email(email))

    def before_attempt(self) -> None:
        # Runs before Argon2: a blocked request costs one small query.
        self._limiter.hit(self._ip_buckets, peek=self._account_buckets)

    def record_failure(self) -> None:
        self._limiter.hit(self._account_buckets)

    def record_success(self) -> None:
        self._limiter.clear(self._account_buckets)


def guard_register(request: Request, settings: Settings) -> None:
    limiter = get_rate_limiter(settings)
    limiter.hit(limiter.buckets(settings.rl_register_ip, _ip(request, settings)))


def guard_refresh(request: Request, db: Session, settings: Settings, raw_token: str | None) -> None:
    """IP limit always; session limit when the cookie maps to a session.

    Runs before rotation, so a limited request never rotates a token, never
    enters the reuse/grace logic and never revokes a session."""
    limiter = get_rate_limiter(settings)
    buckets: list[Bucket] = limiter.buckets(settings.rl_refresh_ip, _ip(request, settings))
    if raw_token:
        session_id = db.scalar(select(RefreshToken.session_id).where(RefreshToken.token_hash == hash_refresh_token(raw_token)))
        if session_id is not None:
            buckets += limiter.buckets(settings.rl_refresh_session, str(session_id))
    limiter.hit(buckets)
