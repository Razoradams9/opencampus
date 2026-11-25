"""Password hashing, access tokens and opaque refresh/CSRF tokens."""

import hashlib
import hmac
import secrets
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

from app.core.config import Settings

# Argon2id with argon2-cffi's RFC 9106 "low memory" profile: t=3, m=64 MiB, p=4.
_hasher = PasswordHasher(time_cost=3, memory_cost=64 * 1024, parallelism=4, hash_len=32, salt_len=16)

# Verified against when the email is unknown, so response time does not
# reveal whether an account exists.
_DUMMY_HASH = _hasher.hash(secrets.token_urlsafe(16))


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password_hash: str | None, password: str) -> bool:
    try:
        return _hasher.verify(password_hash or _DUMMY_HASH, password) and password_hash is not None
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def password_needs_rehash(password_hash: str) -> bool:
    return _hasher.check_needs_rehash(password_hash)


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


# ---- Access tokens (short-lived JWT, held in memory by the client) --------

class TokenError(Exception):
    pass


@dataclass(frozen=True)
class AccessClaims:
    user_id: uuid.UUID
    session_id: uuid.UUID


def create_access_token(settings: Settings, user_id: uuid.UUID, session_id: uuid.UUID, now: datetime | None = None) -> str:
    issued = now or utcnow()
    payload = {
        "iss": settings.jwt_issuer,
        "aud": settings.jwt_audience,
        "sub": str(user_id),
        "sid": str(session_id),
        "typ": "access",
        "iat": int(issued.timestamp()),
        "exp": int((issued + timedelta(seconds=settings.access_token_ttl)).timestamp()),
        "jti": secrets.token_urlsafe(8),
    }
    # Deliberately no role or institution claims: both are resolved from the
    # database on every request so revocations take effect immediately.
    return jwt.encode(payload, settings.jwt_secret, algorithm="HS256")


def decode_access_token(settings: Settings, token: str) -> AccessClaims:
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=["HS256"],  # pinned: rejects "none" and algorithm confusion
            audience=settings.jwt_audience,
            issuer=settings.jwt_issuer,
            options={"require": ["exp", "iat", "sub", "sid", "typ"]},
        )
        if payload["typ"] != "access":
            raise TokenError("wrong token type")
        return AccessClaims(user_id=uuid.UUID(payload["sub"]), session_id=uuid.UUID(payload["sid"]))
    except (jwt.PyJWTError, ValueError, KeyError) as exc:
        raise TokenError(str(exc)) from exc


# ---- Opaque tokens ---------------------------------------------------------

def new_opaque_token() -> str:
    """256 bits of randomness, URL-safe."""
    return secrets.token_urlsafe(32)


def hash_refresh_token(token: str) -> str:
    """SHA-256 is appropriate here (unlike for passwords): the input is a
    256-bit random value, so brute force is infeasible without a slow hash."""
    return hashlib.sha256(token.encode()).hexdigest()


def constant_time_equals(a: str, b: str) -> bool:
    return hmac.compare_digest(a.encode(), b.encode())
