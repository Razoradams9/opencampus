from datetime import timedelta

from sqlalchemy import select, update

from app.core.config import get_settings
from app.core.security import create_access_token, hash_refresh_token, utcnow
from app.db.session import session_factory, set_db_context
from app.models import AuthSession, Membership, MembershipRole, RefreshToken, User
from tests.helpers import PASSWORD, bearer, csrf_headers, login, make_institution, make_user

REGISTER = {
    "email": "Ada.Ng@Example.org",
    "password": "a long enough passphrase",
    "full_name": "  Ada   Ng ",
    "institution_slug": "aldermoor",
}


def set_cookie_headers(response) -> list[str]:
    return response.headers.get_list("set-cookie")


# ---- Registration ---------------------------------------------------------

def test_registration_creates_student_and_signs_in(client):
    make_institution("aldermoor", "Aldermoor College")

    response = client.post("/api/auth/register", json=REGISTER)

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["me"]["user"]["email"] == "ada.ng@example.org"  # normalised
    assert body["me"]["user"]["full_name"] == "Ada Ng"
    assert body["me"]["active_institution"]["slug"] == "aldermoor"
    assert body["me"]["active_institution"]["role"] == "student"
    assert body["me"]["user"]["is_platform_admin"] is False
    assert "password" not in response.text and "hash" not in response.text
    assert response.headers["cache-control"] == "no-store"

    # Refresh cookie: HttpOnly, Secure, SameSite=Strict, scoped to /api/auth.
    settings = get_settings()
    refresh_cookie = next(c for c in set_cookie_headers(response) if c.startswith(settings.refresh_cookie_name))
    lowered = refresh_cookie.lower()
    assert "httponly" in lowered and "secure" in lowered and "samesite=strict" in lowered
    assert "path=/api/auth" in lowered
    # The refresh token is not in the JSON body.
    raw_refresh = client.cookies.get(settings.refresh_cookie_name)
    assert raw_refresh and raw_refresh not in response.text


def test_refresh_tokens_are_stored_hashed(client):
    make_institution("aldermoor")
    client.post("/api/auth/register", json=REGISTER)
    raw = client.cookies.get(get_settings().refresh_cookie_name)

    with session_factory()() as db:
        stored = db.scalars(select(RefreshToken.token_hash)).all()
        password_hash = db.scalar(select(User.password_hash))
    assert stored == [hash_refresh_token(raw)]
    assert raw not in stored
    assert password_hash.startswith("$argon2id$")


def test_registration_cannot_choose_role(client):
    institution = make_institution("aldermoor")

    escalation = client.post("/api/auth/register", json={**REGISTER, "role": "college_admin"})
    assert escalation.status_code == 422  # unknown fields are rejected outright

    client.post("/api/auth/register", json=REGISTER)
    with session_factory()() as db:
        set_db_context(db, tenant_id=institution.id)
        assert db.scalar(select(Membership.role)) == MembershipRole.student


def test_duplicate_account_rejected_case_insensitively(client):
    make_institution("aldermoor")
    assert client.post("/api/auth/register", json=REGISTER).status_code == 201

    again = client.post("/api/auth/register", json={**REGISTER, "email": "ADA.NG@example.org"})

    assert again.status_code == 409
    assert again.json()["code"] == "email_taken"


def test_registration_requires_open_institution(client):
    make_institution("closed", open_registration=False)
    response = client.post("/api/auth/register", json={**REGISTER, "institution_slug": "closed"})
    assert response.status_code == 400
    assert response.json()["code"] == "registration_closed"

    unknown = client.post("/api/auth/register", json={**REGISTER, "institution_slug": "nowhere"})
    assert unknown.status_code == 400  # same answer: no institution enumeration via sign-up


def test_short_password_rejected(client):
    make_institution("aldermoor")
    assert client.post("/api/auth/register", json={**REGISTER, "password": "short"}).status_code == 422


# ---- Login ----------------------------------------------------------------

def test_login_success_and_me(client):
    institution = make_institution("aldermoor")
    make_user("maya@aldermoor.example", [(institution, MembershipRole.student)], name="Maya Okafor")

    token = login(client, "maya@aldermoor.example")
    me = client.get("/api/auth/me", headers=bearer(token))

    assert me.status_code == 200
    assert me.json()["user"]["full_name"] == "Maya Okafor"
    assert me.json()["active_institution"]["role"] == "student"


def test_invalid_password_and_unknown_email_get_same_response(client):
    institution = make_institution("aldermoor")
    make_user("maya@aldermoor.example", [(institution, MembershipRole.student)])

    wrong = client.post("/api/auth/login", json={"email": "maya@aldermoor.example", "password": "wrong password!"})
    unknown = client.post("/api/auth/login", json={"email": "nobody@aldermoor.example", "password": PASSWORD})

    assert wrong.status_code == unknown.status_code == 401
    assert wrong.json() == unknown.json() == {"detail": "Invalid email or password", "code": "invalid_credentials"}
    assert get_settings().refresh_cookie_name not in client.cookies


def test_deactivated_user_cannot_log_in(client):
    user = make_user("gone@aldermoor.example")
    with session_factory()() as db:
        db.execute(update(User).where(User.id == user.id).values(is_active=False))
        db.commit()
    response = client.post("/api/auth/login", json={"email": "gone@aldermoor.example", "password": PASSWORD})
    assert response.status_code == 401


# ---- Access tokens --------------------------------------------------------

def test_missing_or_malformed_token_rejected(client):
    assert client.get("/api/auth/me").status_code == 401
    assert client.get("/api/auth/me", headers=bearer("not-a-jwt")).status_code == 401
    assert client.get("/api/auth/me", headers={"Authorization": "Basic abc"}).status_code == 401


def test_expired_access_token_rejected(client):
    institution = make_institution("aldermoor")
    user = make_user("maya@aldermoor.example", [(institution, MembershipRole.student)])
    login(client, "maya@aldermoor.example")
    with session_factory()() as db:
        session_id = db.scalar(select(AuthSession.id))

    settings = get_settings()
    issued = utcnow() - timedelta(seconds=settings.access_token_ttl + 5)
    expired = create_access_token(settings, user.id, session_id, now=issued)

    response = client.get("/api/auth/me", headers=bearer(expired))
    assert response.status_code == 401
    assert response.json()["code"] == "token_invalid"


def test_token_signed_with_other_key_or_alg_none_rejected(client):
    import jwt

    institution = make_institution("aldermoor")
    user = make_user("maya@aldermoor.example", [(institution, MembershipRole.student)])
    settings = get_settings()
    claims = {"iss": settings.jwt_issuer, "aud": settings.jwt_audience, "sub": str(user.id), "sid": str(user.id),
              "typ": "access", "iat": int(utcnow().timestamp()), "exp": int(utcnow().timestamp()) + 600}

    forged = jwt.encode(claims, "x" * 48, algorithm="HS256")
    unsigned = jwt.encode(claims, None, algorithm="none")

    assert client.get("/api/auth/me", headers=bearer(forged)).status_code == 401
    assert client.get("/api/auth/me", headers=bearer(unsigned)).status_code == 401


# ---- Refresh rotation -----------------------------------------------------

def test_refresh_rotates_token(client):
    institution = make_institution("aldermoor")
    make_user("maya@aldermoor.example", [(institution, MembershipRole.student)])
    login(client, "maya@aldermoor.example")
    name = get_settings().refresh_cookie_name
    first = client.cookies.get(name)

    response = client.post("/api/auth/refresh", headers=csrf_headers(client))

    assert response.status_code == 200, response.text
    second = client.cookies.get(name)
    assert second and second != first
    assert client.get("/api/auth/me", headers=bearer(response.json()["access_token"])).status_code == 200
    with session_factory()() as db:
        old = db.scalar(select(RefreshToken).where(RefreshToken.token_hash == hash_refresh_token(first)))
        assert old.rotated_at is not None


def test_refresh_requires_csrf_header(client):
    institution = make_institution("aldermoor")
    make_user("maya@aldermoor.example", [(institution, MembershipRole.student)])
    login(client, "maya@aldermoor.example")

    missing = client.post("/api/auth/refresh")
    wrong = client.post("/api/auth/refresh", headers={"X-CSRF-Token": "guess"})
    foreign = client.post("/api/auth/refresh", headers={**csrf_headers(client), "Origin": "https://evil.example"})

    assert missing.status_code == wrong.status_code == foreign.status_code == 403
    assert missing.json()["code"] == "csrf_failed"
    assert foreign.json()["code"] == "origin_rejected"


def test_reused_refresh_token_within_grace_is_not_fatal(make_client):
    institution = make_institution("aldermoor")
    make_user("maya@aldermoor.example", [(institution, MembershipRole.student)])
    browser = make_client()
    login(browser, "maya@aldermoor.example")
    name = get_settings().refresh_cookie_name
    old = browser.cookies.get(name)
    csrf = csrf_headers(browser)
    assert browser.post("/api/auth/refresh", headers=csrf).status_code == 200

    # Second tab still holding the old cookie, refreshing at the same moment.
    tab = make_client()
    tab.cookies.set(name, old, domain="testserver.local", path="/api/auth")
    tab.cookies.set(get_settings().csrf_cookie_name, csrf["X-CSRF-Token"], domain="testserver.local")
    raced = tab.post("/api/auth/refresh", headers=csrf)

    assert raced.status_code == 401
    assert raced.json()["code"] == "refresh_superseded"
    # The session survives: the current cookie still works.
    assert browser.post("/api/auth/refresh", headers=csrf_headers(browser)).status_code == 200


def test_reused_refresh_token_after_grace_revokes_session(make_client):
    institution = make_institution("aldermoor")
    make_user("maya@aldermoor.example", [(institution, MembershipRole.student)])
    victim = make_client()
    access = login(victim, "maya@aldermoor.example")
    name = get_settings().refresh_cookie_name
    stolen = victim.cookies.get(name)
    csrf = csrf_headers(victim)
    assert victim.post("/api/auth/refresh", headers=csrf).status_code == 200

    # Age the rotation beyond the grace window.
    with session_factory()() as db:
        db.execute(update(RefreshToken).where(RefreshToken.rotated_at.is_not(None))
                   .values(rotated_at=utcnow() - timedelta(minutes=5)))
        db.commit()

    attacker = make_client()
    attacker.cookies.set(name, stolen, domain="testserver.local", path="/api/auth")
    attacker.cookies.set(get_settings().csrf_cookie_name, csrf["X-CSRF-Token"], domain="testserver.local")
    replay = attacker.post("/api/auth/refresh", headers=csrf)

    assert replay.status_code == 401
    assert replay.json()["code"] == "refresh_reused"
    # Whole session is dead: the victim's current refresh token and access token too.
    assert victim.post("/api/auth/refresh", headers=csrf_headers(victim)).status_code == 401
    assert victim.get("/api/auth/me", headers=bearer(access)).status_code == 401


def test_expired_refresh_token_rejected(client):
    institution = make_institution("aldermoor")
    make_user("maya@aldermoor.example", [(institution, MembershipRole.student)])
    login(client, "maya@aldermoor.example")
    with session_factory()() as db:
        db.execute(update(RefreshToken).values(expires_at=utcnow() - timedelta(seconds=1)))
        db.commit()

    response = client.post("/api/auth/refresh", headers=csrf_headers(client))
    assert response.status_code == 401
    assert response.json()["code"] == "session_expired"


def test_session_absolute_lifetime_enforced(client):
    institution = make_institution("aldermoor")
    make_user("maya@aldermoor.example", [(institution, MembershipRole.student)])
    access = login(client, "maya@aldermoor.example")
    with session_factory()() as db:
        db.execute(update(AuthSession).values(expires_at=utcnow() - timedelta(seconds=1)))
        db.commit()

    assert client.get("/api/auth/me", headers=bearer(access)).status_code == 401
    assert client.post("/api/auth/refresh", headers=csrf_headers(client)).status_code == 401


# ---- Logout and revocation ------------------------------------------------

def test_logout_revokes_session_immediately(client):
    institution = make_institution("aldermoor")
    make_user("maya@aldermoor.example", [(institution, MembershipRole.student)])
    access = login(client, "maya@aldermoor.example")
    name = get_settings().refresh_cookie_name
    refresh_before = client.cookies.get(name)
    csrf = csrf_headers(client)

    response = client.post("/api/auth/logout", headers=csrf)

    assert response.status_code == 204
    assert name not in client.cookies
    # Access token stops working before its expiry, because its session is revoked.
    assert client.get("/api/auth/me", headers=bearer(access)).status_code == 401
    # Replaying the old refresh token fails.
    client.cookies.set(name, refresh_before, domain="testserver.local", path="/api/auth")
    client.cookies.set(get_settings().csrf_cookie_name, csrf["X-CSRF-Token"], domain="testserver.local")
    assert client.post("/api/auth/refresh", headers=csrf).status_code == 401
    with session_factory()() as db:
        assert db.scalar(select(AuthSession.revoke_reason)) == "logout"


def test_user_can_revoke_own_other_session_but_not_others(make_client):
    institution = make_institution("aldermoor")
    make_user("maya@aldermoor.example", [(institution, MembershipRole.student)])
    make_user("lena@aldermoor.example", [(institution, MembershipRole.faculty)])
    laptop, phone, other = make_client(), make_client(), make_client()
    laptop_token = login(laptop, "maya@aldermoor.example")
    phone_token = login(phone, "maya@aldermoor.example")
    other_token = login(other, "lena@aldermoor.example")

    sessions = laptop.get("/api/auth/sessions", headers=bearer(laptop_token)).json()
    assert len(sessions) == 2
    phone_session = next(s for s in sessions if not s["current"])

    assert other.delete(f"/api/auth/sessions/{phone_session['id']}", headers=bearer(other_token)).status_code == 404
    assert laptop.delete(f"/api/auth/sessions/{phone_session['id']}", headers=bearer(laptop_token)).status_code == 204

    assert phone.get("/api/auth/me", headers=bearer(phone_token)).status_code == 401
    assert laptop.get("/api/auth/me", headers=bearer(laptop_token)).status_code == 200


# ---- Open registration (no institution code) -------------------------------

def test_registration_without_institution_joins_open_institution(client):
    body = {k: v for k, v in REGISTER.items() if k != "institution_slug"}

    response = client.post("/api/auth/register", json=body)

    assert response.status_code == 201, response.text
    active = response.json()["me"]["active_institution"]
    assert active["slug"] == "opencampus" and active["name"] == "OpenCampus Community"
    assert active["role"] == "student"  # never more than student
    # A second sign-up reuses the same institution.
    second = client.post("/api/auth/register", json={**body, "email": "second@example.org"})
    assert second.json()["me"]["active_institution"]["id"] == active["id"]


def test_blank_institution_code_counts_as_none(client):
    response = client.post("/api/auth/register", json={**REGISTER, "institution_slug": "   "})
    assert response.status_code == 201
    assert response.json()["me"]["active_institution"]["slug"] == "opencampus"


def test_open_registration_can_be_disabled(app, client):
    import dataclasses

    closed = dataclasses.replace(get_settings(), open_registration_slug="")
    app.dependency_overrides[get_settings] = lambda: closed
    body = {k: v for k, v in REGISTER.items() if k != "institution_slug"}

    response = client.post("/api/auth/register", json=body)

    assert response.status_code == 400
    assert response.json()["code"] == "institution_required"


def test_suspended_open_institution_blocks_sign_up(client):
    body = {k: v for k, v in REGISTER.items() if k != "institution_slug"}
    assert client.post("/api/auth/register", json=body).status_code == 201
    with session_factory()() as db:
        from app.models import Institution, InstitutionStatus

        db.execute(update(Institution).where(Institution.slug == "opencampus").values(status=InstitutionStatus.suspended))
        db.commit()
    blocked = client.post("/api/auth/register", json={**body, "email": "late@example.org"})
    assert blocked.status_code == 400 and blocked.json()["code"] == "registration_closed"


def test_open_registration_is_off_by_default_in_production(monkeypatch):
    from app.core.config import build_settings

    monkeypatch.setenv("OPENCAMPUS_ENV", "production")
    monkeypatch.setenv("OPENCAMPUS_FRONTEND_URL", "https://campus.example")
    monkeypatch.setenv("OPENCAMPUS_EMAIL_MODE", "smtp")
    monkeypatch.setenv("OPENCAMPUS_SMTP_HOST", "mail.example")
    monkeypatch.setenv("OPENCAMPUS_EMAIL_FROM", "no-reply@campus.example")
    monkeypatch.delenv("OPENCAMPUS_OPEN_REGISTRATION", raising=False)
    assert build_settings().open_registration_slug == ""
