"""Password recovery: issue single-use reset tokens and consume them.

Lifecycle: request -> token (256-bit, SHA-256 hash stored, 30 min TTL; any
earlier unused tokens for the user are deleted) -> email with a link whose
token is in the URL fragment -> confirm: atomic single-use consumption,
new Argon2id hash, every session revoked, all in one transaction.
"""

import logging
import uuid
from dataclasses import dataclass
from datetime import timedelta

from sqlalchemy import delete, select, text, update
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.errors import ApiError
from app.core.security import hash_password, hash_refresh_token, new_opaque_token, utcnow
from app.models import AuthSession, PasswordResetToken, User
from app.services.auth import normalise_email
from app.services.email import get_email_sender

log = logging.getLogger("opencampus.password_reset")

GENERIC_REQUEST_MESSAGE = "If an account exists for that email, we've sent a link to reset the password."


@dataclass(frozen=True)
class PendingEmail:
    to: str
    link: str


def hash_reset_token(token: str) -> str:
    # Same construction as refresh tokens: SHA-256 of a 256-bit random value.
    return hash_refresh_token(token)


def request_reset(db: Session, settings: Settings, email: str) -> PendingEmail | None:
    """Create a reset token for an eligible account. Returns the email to send
    (outside the request, so delivery time does not reveal account existence)
    or None. Callers must respond identically in both cases."""
    user = db.scalar(select(User).where(User.email == normalise_email(email)))
    if user is None or not user.is_active:
        return None

    raw = new_opaque_token()  # 32 bytes from the OS CSPRNG
    # Only the newest link works: earlier unused tokens are invalidated.
    db.execute(delete(PasswordResetToken).where(PasswordResetToken.user_id == user.id, PasswordResetToken.used_at.is_(None)))
    db.add(
        PasswordResetToken(
            user_id=user.id,
            token_hash=hash_reset_token(raw),
            expires_at=utcnow() + timedelta(seconds=settings.password_reset_ttl),
        )
    )
    db.commit()
    # Fragment, not query string: never sent to servers, proxies or Referer.
    return PendingEmail(to=user.email, link=f"{settings.frontend_url}/reset-password#token={raw}")


def deliver_reset_email(settings: Settings, pending: PendingEmail) -> None:
    """Background task. Failures are logged without the link or token."""
    minutes = settings.password_reset_ttl // 60
    body = (
        "Someone asked to reset the password for your OpenCampus account.\n\n"
        f"To choose a new password, open this link within {minutes} minutes:\n\n"
        f"{pending.link}\n\n"
        "The link works once. If you didn't ask for this, you can ignore this email:\n"
        "your password stays the same.\n"
    )
    try:
        get_email_sender(settings).send(pending.to, "Reset your OpenCampus password", body)
    except Exception as exc:  # noqa: BLE001 - delivery must never crash or leak
        log.warning("Password reset email delivery failed (%s)", type(exc).__name__)


def confirm_reset(db: Session, token: str, new_password: str) -> uuid.UUID:
    """Consume the token and set the password, atomically. Returns the user id."""
    # Single statement = single use: concurrent confirmations race on the row,
    # and only one sees used_at IS NULL. Expiry is checked in database time.
    user_id = db.execute(
        update(PasswordResetToken)
        .where(
            PasswordResetToken.token_hash == hash_reset_token(token),
            PasswordResetToken.used_at.is_(None),
            PasswordResetToken.expires_at > text("now()"),
        )
        .values(used_at=text("now()"))
        .returning(PasswordResetToken.user_id)
    ).scalar_one_or_none()
    if user_id is None:
        raise ApiError(400, "reset_token_invalid", "This reset link is invalid or has expired. Request a new one.")

    user = db.get(User, user_id)
    if user is None or not user.is_active:
        raise ApiError(400, "reset_token_invalid", "This reset link is invalid or has expired. Request a new one.")

    # The user is taken from the token row only, so a token can never change
    # another account's password.
    user.password_hash = hash_password(new_password)
    db.execute(delete(PasswordResetToken).where(PasswordResetToken.user_id == user_id, PasswordResetToken.used_at.is_(None)))
    # Revoking every session kills their refresh tokens and, because access
    # tokens are checked against the session, their access tokens too.
    db.execute(
        update(AuthSession)
        .where(AuthSession.user_id == user_id, AuthSession.revoked_at.is_(None))
        .values(revoked_at=utcnow(), revoke_reason="password_reset")
    )
    db.commit()  # token consumption, new hash and revocations commit together or not at all
    return user_id


def email_for_user(db: Session, user_id: uuid.UUID) -> str:
    user = db.get(User, user_id)
    assert user is not None
    return user.email
