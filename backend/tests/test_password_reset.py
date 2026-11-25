"""Password recovery, against the real PostgreSQL test database."""

import dataclasses
import logging
import re
import socketserver
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select, update

from app.core.config import ConfigError, RateLimitPolicy, build_settings, get_settings
from app.core.security import hash_refresh_token, utcnow, verify_password
from app.db.session import session_factory
from app.main import create_app
from app.models import AuthSession, MembershipRole, PasswordResetToken, User
from app.services.email import SmtpSender
from tests.helpers import PASSWORD, bearer, csrf_headers, make_institution, make_user

# Counter-based assertions must not straddle a rate-limit window boundary.
pytestmark = pytest.mark.usefixtures("clear_of_window_edge")

BASE_URL = "https://testserver"
NEW_PASSWORD = "a brand new passphrase"
GENERIC = {"message": "If an account exists for that email, we've sent a link to reset the password."}
INVALID = {"detail": "This reset link is invalid or has expired. Request a new one.", "code": "reset_token_invalid"}


def policies(group: str, spec: str) -> tuple[RateLimitPolicy, ...]:
    out = []
    for item in spec.split(","):
        limit, window = (int(x) for x in item.split("/"))
        out.append(RateLimitPolicy(f"{group}:{window}", limit, window))
    return tuple(out)


@pytest.fixture
def mail_dir(tmp_path: Path) -> Path:
    return tmp_path / "mail"


@pytest.fixture
def build(mail_dir: Path):
    clients: list[TestClient] = []

    def factory(ip: str = "203.0.113.10", **overrides) -> TestClient:
        changes = {"email_dev_dir": mail_dir}
        for field, value in overrides.items():
            changes[field] = policies(field.removeprefix("rl_"), value) if field.startswith("rl_") else value
        configured = dataclasses.replace(get_settings(), **changes)
        app = create_app()
        app.dependency_overrides[get_settings] = lambda: configured
        client = TestClient(app, base_url=BASE_URL, client=(ip, 50000))
        clients.append(client)
        return client

    yield factory
    for client in clients:
        client.close()


@pytest.fixture
def maya():
    institution = make_institution("aldermoor")
    return make_user("maya@aldermoor.example", [(institution, MembershipRole.student)], name="Maya Okafor")


def request_reset(client: TestClient, email: str = "maya@aldermoor.example", **headers):
    return client.post("/api/auth/password-reset/request", json={"email": email}, headers=headers)


def confirm(client: TestClient, token: str, password: str = NEW_PASSWORD):
    return client.post("/api/auth/password-reset/confirm", json={"token": token, "new_password": password})


def emails(mail_dir: Path) -> list[str]:
    return [p.read_text() for p in sorted(mail_dir.glob("*.eml"))] if mail_dir.is_dir() else []


def token_from(mail: str) -> str:
    match = re.search(r"/reset-password#token=([A-Za-z0-9_-]+)", mail)
    assert match, mail
    return match.group(1)


def count(model) -> int:
    with session_factory()() as db:
        return db.scalar(select(func.count()).select_from(model))


def login(client: TestClient, password: str, email: str = "maya@aldermoor.example"):
    return client.post("/api/auth/login", json={"email": email, "password": password})


# ---- 1/2/3. Requests: existing vs unknown ----------------------------------

def test_request_for_existing_account_creates_token_and_email(build, maya, mail_dir):
    response = request_reset(build())

    assert response.status_code == 202 and response.json() == GENERIC
    assert count(PasswordResetToken) == 1
    [mail] = emails(mail_dir)
    assert "To: maya@aldermoor.example" in mail
    assert "Subject: Reset your OpenCampus password" in mail
    assert "http://localhost:5173/reset-password#token=" in mail


def test_request_for_unknown_account_does_nothing_visible(build, maya, mail_dir):
    response = request_reset(build(), "ghost@aldermoor.example")

    assert response.status_code == 202 and response.json() == GENERIC
    assert count(PasswordResetToken) == 0
    assert emails(mail_dir) == []


def test_public_responses_are_identical(build, maya):
    inactive = make_user("gone@aldermoor.example")
    with session_factory()() as db:
        db.execute(update(User).where(User.id == inactive.id).values(is_active=False))
        db.commit()

    def shape(response):
        headers = {k: v for k, v in response.headers.items() if k not in {"date"}}
        return response.status_code, response.json(), headers

    existing = shape(request_reset(build(ip="198.51.100.1")))
    unknown = shape(request_reset(build(ip="198.51.100.2"), "ghost@aldermoor.example"))
    deactivated = shape(request_reset(build(ip="198.51.100.3"), "gone@aldermoor.example"))
    assert existing == unknown == deactivated


def test_link_uses_configured_frontend_not_the_host_header(build, maya, mail_dir):
    request_reset(build(), Host="evil.example", **{"X-Forwarded-Host": "evil.example"})
    [mail] = emails(mail_dir)
    assert "evil.example" not in mail
    assert "http://localhost:5173/reset-password#token=" in mail


def test_new_request_invalidates_the_previous_link(build, maya, mail_dir):
    client = build()
    request_reset(client)
    request_reset(client)
    first, second = (token_from(m) for m in emails(mail_dir))
    assert count(PasswordResetToken) == 1
    assert confirm(client, first).json() == INVALID
    assert confirm(client, second).status_code == 200


# ---- 4. Storage ------------------------------------------------------------

def test_only_token_hashes_are_stored(build, maya, mail_dir):
    request_reset(build())
    raw = token_from(emails(mail_dir)[0])
    with session_factory()() as db:
        row = db.scalar(select(PasswordResetToken))
    assert row.token_hash == hash_refresh_token(raw)
    assert raw not in row.token_hash and len(row.token_hash) == 64
    assert len(raw) >= 43  # 32 random bytes, base64url
    assert timedelta(minutes=29) < row.expires_at - row.created_at <= timedelta(minutes=30, seconds=5)


# ---- 5/10/11. Valid tokens -------------------------------------------------

def test_valid_token_changes_password_with_argon2id(build, maya, mail_dir):
    client = build()
    request_reset(client)
    response = confirm(client, token_from(emails(mail_dir)[0]))

    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    with session_factory()() as db:
        stored = db.scalar(select(User.password_hash).where(User.id == maya.id))
    assert stored.startswith("$argon2id$")
    assert verify_password(stored, NEW_PASSWORD)
    assert login(build(ip="198.51.100.9"), NEW_PASSWORD).status_code == 200
    assert login(build(ip="198.51.100.8"), PASSWORD).status_code == 401


def test_token_cannot_change_another_users_password(build, maya, mail_dir):
    institution_user = make_user("lena@aldermoor.example")
    client = build()
    request_reset(client)
    confirm(client, token_from(emails(mail_dir)[0]))
    with session_factory()() as db:
        lena_hash = db.scalar(select(User.password_hash).where(User.id == institution_user.id))
    assert verify_password(lena_hash, PASSWORD)


def test_reset_password_must_meet_policy(build, maya, mail_dir):
    client = build()
    request_reset(client)
    response = confirm(client, token_from(emails(mail_dir)[0]), password="short")
    assert response.status_code == 422
    # The token was not consumed by the rejected attempt.
    assert confirm(client, token_from(emails(mail_dir)[0])).status_code == 200


# ---- 6/7/8/9. Invalid, expired, reused, concurrent -------------------------

def test_invalid_token_rejected(build, maya):
    assert confirm(build(), "x" * 43).json() == INVALID
    assert confirm(build(), "x" * 43).status_code == 400


def test_expired_token_rejected(build, maya, mail_dir):
    client = build()
    request_reset(client)
    with session_factory()() as db:
        db.execute(update(PasswordResetToken).values(
            created_at=utcnow() - timedelta(hours=1), expires_at=utcnow() - timedelta(seconds=1)
        ))
        db.commit()
    response = confirm(client, token_from(emails(mail_dir)[0]))
    assert response.status_code == 400 and response.json() == INVALID


def test_reused_token_rejected(build, maya, mail_dir):
    client = build()
    request_reset(client)
    token = token_from(emails(mail_dir)[0])
    assert confirm(client, token).status_code == 200
    second = confirm(client, token, password="yet another passphrase")
    assert second.status_code == 400 and second.json() == INVALID
    with session_factory()() as db:
        assert verify_password(db.scalar(select(User.password_hash)), NEW_PASSWORD)


def test_concurrent_confirmations_consume_the_token_once(build, maya, mail_dir):
    request_reset(build())
    token = token_from(emails(mail_dir)[0])
    passwords = [f"concurrent passphrase {i}" for i in range(6)]
    barrier = threading.Barrier(len(passwords))

    def attempt(password: str) -> int:
        client = build(ip="198.51.100.20")
        barrier.wait()
        return confirm(client, token, password).status_code

    with ThreadPoolExecutor(max_workers=len(passwords)) as pool:
        statuses = list(pool.map(attempt, passwords))

    assert sorted(statuses) == [200] + [400] * 5
    winner = passwords[statuses.index(200)]
    with session_factory()() as db:
        stored = db.scalar(select(User.password_hash).where(User.id == maya.id))
        assert db.scalar(select(func.count()).select_from(PasswordResetToken).where(PasswordResetToken.used_at.is_not(None))) == 1
    assert verify_password(stored, winner)


# ---- 12/13. Sessions and refresh tokens revoked ----------------------------

def test_reset_revokes_all_sessions_access_and_refresh_tokens(build, maya, mail_dir):
    laptop, phone = build(ip="198.51.100.1"), build(ip="198.51.100.2")
    laptop_access = login(laptop, PASSWORD).json()["access_token"]
    phone_access = login(phone, PASSWORD).json()["access_token"]
    phone_csrf = csrf_headers(phone)

    requester = build(ip="198.51.100.3")
    request_reset(requester)
    assert confirm(requester, token_from(emails(mail_dir)[0])).status_code == 200

    # Access tokens stop working immediately (session check), well before expiry.
    assert laptop.get("/api/auth/me", headers=bearer(laptop_access)).status_code == 401
    assert phone.get("/api/auth/me", headers=bearer(phone_access)).status_code == 401
    # Refresh tokens are dead too.
    refresh = phone.post("/api/auth/refresh", headers=phone_csrf)
    assert refresh.status_code == 401
    with session_factory()() as db:
        reasons = set(db.scalars(select(AuthSession.revoke_reason)).all())
    assert reasons == {"password_reset"}


def test_confirm_clears_cookies_in_the_resetting_browser(build, maya, mail_dir):
    client = build()
    login(client, PASSWORD)
    request_reset(client)
    response = confirm(client, token_from(emails(mail_dir)[0]))
    cookies = " ".join(response.headers.get_list("set-cookie")).lower()
    assert get_settings().refresh_cookie_name.lower() in cookies and "max-age=0" in cookies


def test_reset_lifts_login_failure_lock(build, maya, mail_dir):
    for i in range(5):
        login(build(ip=f"198.51.100.{i + 1}"), "wrong password!!")
    assert login(build(ip="198.51.100.50"), PASSWORD).status_code == 429
    client = build(ip="198.51.100.60")
    request_reset(client)
    confirm(client, token_from(emails(mail_dir)[0]))
    assert login(build(ip="198.51.100.70"), NEW_PASSWORD).status_code == 200


# ---- 14/15. Rate limiting --------------------------------------------------

def test_reset_requests_limited_per_email_without_enumeration(build, maya):
    existing = [request_reset(build(ip=f"198.51.100.{i + 1}")) for i in range(4)]
    unknown = [request_reset(build(ip=f"198.51.100.{i + 101}"), "ghost@aldermoor.example") for i in range(4)]

    assert [r.status_code for r in existing] == [202, 202, 202, 429]
    assert [r.status_code for r in unknown] == [202, 202, 202, 429]
    assert existing[3].json() == unknown[3].json() == {
        "detail": "Too many attempts. Please wait and try again.", "code": "rate_limit_exceeded"
    }
    assert "retry-after" in existing[3].headers
    assert count(PasswordResetToken) == 1  # earlier tokens were replaced, the 4th never issued


def test_reset_requests_limited_per_ip(build, maya):
    client = build(rl_reset_request_ip="2/900,100/3600")
    assert request_reset(client, "a@aldermoor.example").status_code == 202
    assert request_reset(client, "b@aldermoor.example").status_code == 202
    assert request_reset(client, "c@aldermoor.example").status_code == 429


def test_reset_confirmations_limited_per_ip(build, maya):
    client = build(rl_reset_confirm_ip="2/900,100/3600")
    assert confirm(client, "y" * 43).status_code == 400
    assert confirm(client, "y" * 43).status_code == 400
    assert confirm(client, "y" * 43).status_code == 429


# ---- 16. Development sink and logging --------------------------------------

def test_dev_sink_writes_email_and_logs_never_contain_the_token(build, maya, mail_dir, caplog):
    caplog.set_level(logging.DEBUG)
    client = build()
    request_reset(client)
    [mail] = emails(mail_dir)
    token = token_from(mail)
    confirm(client, token)

    assert token not in caplog.text
    assert "Development email for *@aldermoor.example written to" in caplog.text
    assert "maya@" not in caplog.text  # only the domain is logged


# ---- 17. SMTP configuration and delivery -----------------------------------

@pytest.mark.parametrize(
    ("env", "message"),
    [
        ({"OPENCAMPUS_EMAIL_MODE": "smtp"}, "OPENCAMPUS_SMTP_HOST is required"),
        ({"OPENCAMPUS_EMAIL_MODE": "smtp", "OPENCAMPUS_SMTP_HOST": "mail.example"}, "OPENCAMPUS_EMAIL_FROM is required"),
        ({"OPENCAMPUS_EMAIL_MODE": "carrier-pigeon"}, "must be 'dev_file' or 'smtp'"),
        ({"OPENCAMPUS_EMAIL_MODE": "dev_file", "OPENCAMPUS_ENV": "production",
          "OPENCAMPUS_FRONTEND_URL": "https://campus.example"}, "dev_file is not allowed in production"),
        ({"OPENCAMPUS_EMAIL_MODE": "smtp", "OPENCAMPUS_SMTP_HOST": "mail.example", "OPENCAMPUS_EMAIL_FROM": "a@b.example",
          "OPENCAMPUS_SMTP_TLS": "none", "OPENCAMPUS_ENV": "production", "OPENCAMPUS_FRONTEND_URL": "https://campus.example"},
         "OPENCAMPUS_SMTP_TLS=none is not allowed in production"),
        ({"OPENCAMPUS_EMAIL_MODE": "smtp", "OPENCAMPUS_SMTP_HOST": "mail.example", "OPENCAMPUS_EMAIL_FROM": "a@b.example",
          "OPENCAMPUS_SMTP_USERNAME": "user"}, "Set both OPENCAMPUS_SMTP_USERNAME and OPENCAMPUS_SMTP_PASSWORD"),
        ({"OPENCAMPUS_EMAIL_MODE": "smtp", "OPENCAMPUS_SMTP_HOST": "mail.example", "OPENCAMPUS_EMAIL_FROM": "a@b.example",
          "OPENCAMPUS_SMTP_USERNAME": "user", "OPENCAMPUS_SMTP_PASSWORD": "pw", "OPENCAMPUS_SMTP_TLS": "none"},
         "without TLS"),
        ({"OPENCAMPUS_SMTP_PORT": "abc", "OPENCAMPUS_EMAIL_MODE": "smtp"}, "OPENCAMPUS_SMTP_PORT must be a number"),
        ({"OPENCAMPUS_SMTP_PORT": "70000"}, "between 1 and 65535"),
        ({"OPENCAMPUS_ENV": "production", "OPENCAMPUS_FRONTEND_URL": ""}, "OPENCAMPUS_FRONTEND_URL must be set in production"),
        ({"OPENCAMPUS_ENV": "production", "OPENCAMPUS_FRONTEND_URL": "http://campus.example"}, "must use https in production"),
        ({"OPENCAMPUS_FRONTEND_URL": "javascript:alert(1)"}, "absolute http(s) URL"),
    ],
)
def test_email_configuration_errors(monkeypatch, env, message):
    monkeypatch.setenv("OPENCAMPUS_EMAIL_MODE", "dev_file")
    for name, value in env.items():
        monkeypatch.setenv(name, value)
    with pytest.raises(ConfigError, match=re.escape(message)):
        build_settings()


def test_smtp_password_is_not_shown_in_settings_repr(monkeypatch):
    for name, value in {"OPENCAMPUS_EMAIL_MODE": "smtp", "OPENCAMPUS_SMTP_HOST": "mail.example",
                        "OPENCAMPUS_EMAIL_FROM": "a@b.example", "OPENCAMPUS_SMTP_USERNAME": "user",
                        "OPENCAMPUS_SMTP_PASSWORD": "hunter2-very-secret"}.items():
        monkeypatch.setenv(name, value)
    assert "hunter2-very-secret" not in repr(build_settings())


class _FakeSmtp(socketserver.StreamRequestHandler):
    """Just enough SMTP to receive one message (no TLS; local test only)."""

    received: list[str] = []

    def handle(self):
        self.wfile.write(b"220 fake ESMTP\r\n")
        while line := self.rfile.readline():
            command = line.decode().strip().upper()
            if command.startswith(("EHLO", "HELO")):
                self.wfile.write(b"250 fake\r\n")
            elif command == "DATA":
                self.wfile.write(b"354 go\r\n")
                data = []
                while (chunk := self.rfile.readline()) not in (b".\r\n", b""):
                    data.append(chunk.decode())
                _FakeSmtp.received.append("".join(data))
                self.wfile.write(b"250 queued\r\n")
            elif command == "QUIT":
                self.wfile.write(b"221 bye\r\n")
                return
            else:
                self.wfile.write(b"250 ok\r\n")


def test_smtp_delivery_end_to_end(build, maya):
    _FakeSmtp.received = []
    server = socketserver.ThreadingTCPServer(("127.0.0.1", 0), _FakeSmtp)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        client = build(email_mode="smtp", smtp_host="127.0.0.1", smtp_port=server.server_address[1],
                       smtp_tls="none", email_from="OpenCampus <no-reply@campus.example>")
        assert request_reset(client).status_code == 202
    finally:
        server.shutdown()
        server.server_close()
    [message] = _FakeSmtp.received
    assert "To: maya@aldermoor.example" in message
    assert "/reset-password#token=" in message


def test_smtp_failure_keeps_the_generic_response_and_logs_no_token(build, maya, caplog):
    caplog.set_level(logging.WARNING)
    client = build(email_mode="smtp", smtp_host="127.0.0.1", smtp_port=9, smtp_tls="none",
                   email_from="no-reply@campus.example")
    response = request_reset(client)
    assert response.status_code == 202 and response.json() == GENERIC
    assert "Password reset email delivery failed" in caplog.text
    assert "reset-password#token=" not in caplog.text


def test_smtp_sender_uses_tls_settings():
    settings = dataclasses.replace(get_settings(), email_mode="smtp", smtp_host="127.0.0.1", smtp_port=9, smtp_tls="ssl")
    with pytest.raises(OSError):  # connection refused before any plaintext is sent
        SmtpSender(settings).send("a@b.example", "s", "b")
