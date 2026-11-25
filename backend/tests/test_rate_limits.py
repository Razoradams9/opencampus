"""Authentication rate limiting, against the real PostgreSQL test database.

Limits are adjusted per test through FastAPI's settings dependency, so no test
waits for a real-world window to pass. Concurrency, persistence and failure
tests use real connections, never a mocked database.
"""

import dataclasses
import threading
from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select, text
from starlette.requests import Request

from app.core.client_ip import client_ip
from app.core.config import RateLimitPolicy, get_settings
from app.core.errors import ApiError
from app.db.session import dispose_engine, session_factory
from app.main import create_app
from app.models import AuthSession, MembershipRole, RateLimitBucket, RefreshToken, User
from app.services.rate_limit import RateLimiter
from tests.helpers import PASSWORD, bearer, csrf_headers, make_institution, make_user

BASE_URL = "https://testserver"
WRONG = "definitely not the password"


def policies(group: str, spec: str) -> tuple[RateLimitPolicy, ...]:
    out = []
    for item in spec.split(","):
        limit, window = (int(x) for x in item.split("/"))
        out.append(RateLimitPolicy(f"{group}:{window}", limit, window))
    return tuple(out)


@pytest.fixture
def build():
    """build(ip=..., **overrides) -> TestClient with its own app and settings."""
    clients: list[TestClient] = []

    def factory(ip: str = "203.0.113.10", **overrides) -> TestClient:
        settings = get_settings()
        changes = {}
        for field, value in overrides.items():
            changes[field] = policies(field.removeprefix("rl_"), value) if field.startswith("rl_") else value
        configured = dataclasses.replace(settings, **changes)
        app = create_app()
        app.dependency_overrides[get_settings] = lambda: configured
        client = TestClient(app, base_url=BASE_URL, client=(ip, 50000))
        clients.append(client)
        return client

    yield factory
    for client in clients:
        client.close()


@pytest.fixture
def college():
    institution = make_institution("aldermoor")
    make_user("maya@aldermoor.example", [(institution, MembershipRole.student)])
    make_user("lena@aldermoor.example", [(institution, MembershipRole.faculty)])
    return institution


def login(client: TestClient, email: str = "maya@aldermoor.example", password: str = PASSWORD):
    return client.post("/api/auth/login", json={"email": email, "password": password})


def assert_rate_limited(response, *, max_retry: int | None = None, min_retry: int = 1):
    assert response.status_code == 429, response.text
    assert response.json() == {"detail": "Too many attempts. Please wait and try again.", "code": "rate_limit_exceeded"}
    retry_after = int(response.headers["retry-after"])
    assert retry_after >= min_retry
    if max_retry is not None:
        assert retry_after <= max_retry


def count(model) -> int:
    with session_factory()() as db:
        return db.scalar(select(func.count()).select_from(model))


# ---- 1. Login keeps working ------------------------------------------------

def test_normal_login_works_and_does_not_count_account_failures(build, college):
    client = build()
    assert login(client).status_code == 200
    with session_factory()() as db:
        # Only the two IP buckets exist; no failure bucket was created.
        assert db.scalar(select(func.count()).select_from(RateLimitBucket)) == 2


# ---- 2/3. Login IP limits --------------------------------------------------

def test_login_ip_minute_limit(build, college):
    client = build()  # defaults: 5/min, 20/hour per IP
    for i in range(5):  # distinct emails isolate the IP limit from account limits
        assert login(client, f"nobody{i}@aldermoor.example", WRONG).status_code == 401
    assert_rate_limited(login(client, "nobody5@aldermoor.example", WRONG), max_retry=60)
    # The correct password is blocked too: the check happens before Argon2.
    assert_rate_limited(login(client), max_retry=60)


def test_login_ip_hourly_limit(build, college):
    client = build(rl_login_ip="100/60,3/3600")
    for i in range(3):
        assert login(client, f"nobody{i}@aldermoor.example", WRONG).status_code == 401
    response = login(client, "nobody3@aldermoor.example", WRONG)
    assert_rate_limited(response, max_retry=3600)


# ---- 4/5/13. Account-identifier failure limits -----------------------------

def test_failed_attempts_per_account_are_limited_across_ips(build, college):
    # Five failures from five different addresses: IP limits never trigger.
    for i in range(5):
        assert login(build(ip=f"198.51.100.{i + 1}"), password=WRONG).status_code == 401
    # Sixth attempt, fresh IP, *correct* password: blocked without verifying it.
    assert_rate_limited(login(build(ip="198.51.100.99")), max_retry=900)
    # Another account is unaffected (independent buckets).
    assert login(build(ip="198.51.100.100"), "lena@aldermoor.example").status_code == 200


def test_account_hourly_failure_limit(build, college):
    for i in range(3):
        client = build(ip=f"198.51.100.{i + 1}", rl_login_account="100/900,3/3600")
        assert login(client, password=WRONG).status_code == 401
    client = build(ip="198.51.100.50", rl_login_account="100/900,3/3600")
    assert_rate_limited(login(client, password=WRONG), min_retry=1, max_retry=3600)


def test_successful_login_clears_failure_count(build, college):
    for i in range(4):
        assert login(build(ip=f"198.51.100.{i + 1}"), password=WRONG).status_code == 401
    assert login(build(ip="198.51.100.20")).status_code == 200
    # Counter reset: four more failures are allowed again.
    for i in range(4):
        assert login(build(ip=f"198.51.100.{i + 30}"), password=WRONG).status_code == 401


def test_unknown_and_wrong_password_are_indistinguishable_including_when_limited(build, college):
    existing, unknown = [], []
    for i in range(6):
        existing.append(login(build(ip=f"198.51.100.{i + 1}"), "maya@aldermoor.example", WRONG))
        unknown.append(login(build(ip=f"198.51.100.{i + 101}"), "ghost@aldermoor.example", WRONG))

    for a, b in zip(existing[:5], unknown[:5]):
        assert a.status_code == b.status_code == 401
        assert a.json() == b.json() == {"detail": "Invalid email or password", "code": "invalid_credentials"}
    # Both reach the limit at the same point, with the same body.
    assert existing[5].status_code == unknown[5].status_code == 429
    assert existing[5].json() == unknown[5].json()
    assert set(existing[5].headers) >= {"retry-after"} and set(unknown[5].headers) >= {"retry-after"}


def test_not_a_member_is_not_counted_as_a_failure(build, college):
    make_institution("halvard")
    client = build(rl_login_ip="100/60,100/3600")
    for _ in range(6):
        response = client.post(
            "/api/auth/login", json={"email": "maya@aldermoor.example", "password": PASSWORD, "institution_slug": "halvard"}
        )
        assert response.status_code == 403  # correct password: never a failed-authentication count
    assert login(client).status_code == 200


# ---- 6. Registration -------------------------------------------------------

def test_registration_ip_limit_applies_before_account_creation(build):
    make_institution("aldermoor")
    client = build()  # default 3/hour

    def register(i: int):
        return client.post(
            "/api/auth/register",
            json={"email": f"new{i}@aldermoor.example", "password": "a long enough passphrase",
                  "full_name": "New Student", "institution_slug": "aldermoor"},
        )

    for i in range(3):
        assert register(i).status_code == 201
    users_before = count(User)
    assert_rate_limited(register(3), max_retry=3600)
    assert count(User) == users_before  # nothing created, no hashing done


# ---- 7/8. Refresh limits ---------------------------------------------------

def test_refresh_session_minute_limit_does_not_rotate_or_revoke(build, college):
    client = build(rl_refresh_session="3/60,100/3600")
    assert login(client).status_code == 200
    for _ in range(3):
        assert client.post("/api/auth/refresh", headers=csrf_headers(client)).status_code == 200
    current = client.cookies.get(get_settings().refresh_cookie_name)

    assert_rate_limited(client.post("/api/auth/refresh", headers=csrf_headers(client)), max_retry=60)

    with session_factory()() as db:
        session = db.scalar(select(AuthSession))
        token = db.scalar(select(RefreshToken).where(RefreshToken.rotated_at.is_(None)))
    assert session.revoked_at is None  # rate limiting never revokes
    from app.core.security import hash_refresh_token

    assert token.token_hash == hash_refresh_token(current)  # and never rotates


def test_refresh_session_hourly_limit(build, college):
    client = build(rl_refresh_session="100/60,2/3600")
    login(client)
    for _ in range(2):
        assert client.post("/api/auth/refresh", headers=csrf_headers(client)).status_code == 200
    assert_rate_limited(client.post("/api/auth/refresh", headers=csrf_headers(client)), max_retry=3600)


def test_refresh_session_limit_follows_the_session_not_the_ip(build, college):
    laptop = build(ip="198.51.100.1", rl_refresh_session="2/60,100/3600")
    login(laptop)
    for _ in range(2):
        assert laptop.post("/api/auth/refresh", headers=csrf_headers(laptop)).status_code == 200
    # Another device (other IP, other session) refreshes freely.
    phone = build(ip="198.51.100.2", rl_refresh_session="2/60,100/3600")
    login(phone)
    assert phone.post("/api/auth/refresh", headers=csrf_headers(phone)).status_code == 200


def test_refresh_ip_limit(build, college):
    client = build(rl_refresh_ip="2/60,100/3600")
    login(client)
    for _ in range(2):
        assert client.post("/api/auth/refresh", headers=csrf_headers(client)).status_code == 200
    assert_rate_limited(client.post("/api/auth/refresh", headers=csrf_headers(client)))


# ---- 9/10. Grace window and reuse detection are preserved ------------------

def test_parallel_tab_refreshes_still_use_the_grace_window(build, college):
    client = build()
    login(client)
    name = get_settings().refresh_cookie_name
    old, csrf = client.cookies.get(name), csrf_headers(client)
    assert client.post("/api/auth/refresh", headers=csrf).status_code == 200

    tab = build()
    tab.cookies.set(name, old, domain="testserver.local", path="/api/auth")
    tab.cookies.set(get_settings().csrf_cookie_name, csrf["X-CSRF-Token"], domain="testserver.local")
    raced = tab.post("/api/auth/refresh", headers=csrf)
    assert raced.status_code == 401 and raced.json()["code"] == "refresh_superseded"
    assert client.post("/api/auth/refresh", headers=csrf_headers(client)).status_code == 200


def test_concurrent_refreshes_of_one_token_rotate_once_and_never_revoke(build, college):
    client = build()
    login(client)
    name = get_settings().refresh_cookie_name
    token, csrf = client.cookies.get(name), csrf_headers(client)

    def refresh_once(_: int):
        tab = build()
        tab.cookies.set(name, token, domain="testserver.local", path="/api/auth")
        tab.cookies.set(get_settings().csrf_cookie_name, csrf["X-CSRF-Token"], domain="testserver.local")
        response = tab.post("/api/auth/refresh", headers=csrf)
        return response.status_code, response.json().get("code")

    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(refresh_once, range(4)))

    assert sorted(status for status, _ in results) == [200, 401, 401, 401]
    assert {code for status, code in results if status == 401} == {"refresh_superseded"}
    with session_factory()() as db:
        assert db.scalar(select(AuthSession.revoked_at)) is None


def test_reuse_detection_still_revokes_after_grace(build, college):
    from datetime import timedelta

    from sqlalchemy import update

    from app.core.security import utcnow

    victim = build()
    access = login(victim).json()["access_token"]
    name = get_settings().refresh_cookie_name
    stolen, csrf = victim.cookies.get(name), csrf_headers(victim)
    assert victim.post("/api/auth/refresh", headers=csrf).status_code == 200
    with session_factory()() as db:
        db.execute(update(RefreshToken).where(RefreshToken.rotated_at.is_not(None)).values(rotated_at=utcnow() - timedelta(minutes=5)))
        db.commit()

    attacker = build(ip="198.51.100.66")
    attacker.cookies.set(name, stolen, domain="testserver.local", path="/api/auth")
    attacker.cookies.set(get_settings().csrf_cookie_name, csrf["X-CSRF-Token"], domain="testserver.local")
    replay = attacker.post("/api/auth/refresh", headers=csrf)
    assert replay.status_code == 401 and replay.json()["code"] == "refresh_reused"
    assert victim.get("/api/auth/me", headers=bearer(access)).status_code == 401


# ---- 11. Logout and revocation ---------------------------------------------

def test_logout_still_works_while_login_is_rate_limited(build, college):
    client = build()
    access = login(client).json()["access_token"]
    for i in range(5):
        login(client, f"nobody{i}@aldermoor.example", WRONG)  # exhaust the IP login limit
    assert_rate_limited(login(client))
    assert client.post("/api/auth/logout", headers=csrf_headers(client)).status_code == 204
    assert client.get("/api/auth/me", headers=bearer(access)).status_code == 401


# ---- 12. Independent IP buckets --------------------------------------------

def test_different_ips_have_independent_buckets(build, college):
    a, b = build(ip="198.51.100.1"), build(ip="198.51.100.2")
    for i in range(5):
        login(a, f"nobody{i}@aldermoor.example", WRONG)
    assert_rate_limited(login(a, "x@aldermoor.example", WRONG))
    assert login(b).status_code == 200


# ---- 14. Concurrency -------------------------------------------------------

def test_concurrent_hits_cannot_exceed_the_limit():
    limiter = RateLimiter(get_settings().rate_limit_secret)
    buckets = limiter.buckets((RateLimitPolicy("test:60", 5, 60),), "shared-identity")
    barrier = threading.Barrier(20)

    def attempt(_: int) -> bool:
        barrier.wait()  # release all 20 at once
        try:
            limiter.hit(buckets)
            return True
        except ApiError as error:
            assert error.status == 429
            return False

    with ThreadPoolExecutor(max_workers=20) as pool:
        allowed = sum(pool.map(attempt, range(20)))
    assert allowed == 5


def test_concurrent_registrations_respect_the_limit(build):
    make_institution("aldermoor")
    client = build()

    def register(i: int) -> int:
        return client.post(
            "/api/auth/register",
            json={"email": f"burst{i}@aldermoor.example", "password": "a long enough passphrase",
                  "full_name": "Burst", "institution_slug": "aldermoor"},
        ).status_code

    with ThreadPoolExecutor(max_workers=8) as pool:
        statuses = list(pool.map(register, range(8)))
    assert statuses.count(201) == 3
    assert statuses.count(429) == 5
    assert count(User) == 3


# ---- 15. Persistence across restarts ---------------------------------------

def test_limits_survive_a_backend_restart(build, college):
    client = build()
    for i in range(5):
        login(client, f"nobody{i}@aldermoor.example", WRONG)
    client.close()

    dispose_engine()  # drop every pooled connection, as a process restart would
    restarted = build()  # brand-new app instance, same client IP
    assert_rate_limited(login(restarted))


# ---- 16. Cleanup -----------------------------------------------------------

def test_expired_buckets_are_purged_and_live_ones_kept(owner_engine):
    with owner_engine.begin() as conn:
        conn.execute(text(
            "INSERT INTO rate_limit_buckets (key_hash, window_start, count, expires_at) VALUES "
            "(repeat('a', 64), now() - interval '2 hours', 3, now() - interval '1 hour'), "
            "(repeat('b', 64), now() - interval '10 minutes', 2, now() + interval '50 minutes')"
        ))
    deleted = RateLimiter(get_settings().rate_limit_secret).purge_expired()
    assert deleted == 1
    with owner_engine.connect() as conn:
        assert conn.execute(text("SELECT key_hash FROM rate_limit_buckets")).scalars().all() == ["b" * 64]


# ---- 17. Client identity cannot be spoofed ---------------------------------

def make_request(peer: str, forwarded: str | None = None) -> Request:
    headers = [(b"x-forwarded-for", forwarded.encode())] if forwarded else []
    return Request({"type": "http", "client": (peer, 1234), "headers": headers})


def test_untrusted_forwarded_headers_are_ignored(build, college):
    client = build()  # no trusted proxies configured
    for i in range(5):
        response = client.post(
            "/api/auth/login",
            json={"email": f"nobody{i}@aldermoor.example", "password": WRONG},
            headers={"X-Forwarded-For": f"192.0.2.{i}", "Forwarded": f"for=192.0.2.{i}"},
        )
        assert response.status_code == 401
    spoofed = client.post(
        "/api/auth/login", json={"email": "x@aldermoor.example", "password": WRONG}, headers={"X-Forwarded-For": "192.0.2.200"}
    )
    assert_rate_limited(spoofed)


def test_client_ip_resolution_rules():
    import ipaddress

    proxies = (ipaddress.ip_network("10.0.0.0/8"),)
    # Untrusted peer: header ignored.
    assert client_ip(make_request("203.0.113.9", "198.51.100.1"), proxies) == "203.0.113.9"
    assert client_ip(make_request("203.0.113.9", "198.51.100.1"), ()) == "203.0.113.9"
    # Trusted proxy: right-most untrusted hop wins; client-written entries to its left are ignored.
    assert client_ip(make_request("10.0.0.2", "6.6.6.6, 198.51.100.7"), proxies) == "198.51.100.7"
    assert client_ip(make_request("10.0.0.2", "6.6.6.6, 198.51.100.7, 10.0.0.9"), proxies) == "198.51.100.7"
    # Trusted proxy without a header, or with garbage: fall back to the proxy itself.
    assert client_ip(make_request("10.0.0.2"), proxies) == "10.0.0.2"
    assert client_ip(make_request("10.0.0.2", "not-an-ip"), proxies) == "10.0.0.2"
    # IPv6 clients are grouped by /64.
    assert client_ip(make_request("2001:db8:1:2:aaaa::1"), ()) == "2001:db8:1:2::/64"
    assert client_ip(make_request("2001:db8:1:2:bbbb::9"), ()) == "2001:db8:1:2::/64"


def test_trusted_proxy_gives_each_client_its_own_bucket(build, college):
    import ipaddress

    trusted = (ipaddress.ip_network("10.0.0.0/8"),)
    proxy = build(ip="10.0.0.2", trusted_proxies=trusted)
    for i in range(5):
        proxy.post(
            "/api/auth/login",
            json={"email": f"nobody{i}@aldermoor.example", "password": WRONG},
            headers={"X-Forwarded-For": "198.51.100.1"},
        )
    blocked = proxy.post(
        "/api/auth/login", json={"email": "x@aldermoor.example", "password": WRONG}, headers={"X-Forwarded-For": "198.51.100.1"}
    )
    assert_rate_limited(blocked)
    other_client = proxy.post(
        "/api/auth/login", json={"email": "maya@aldermoor.example", "password": PASSWORD}, headers={"X-Forwarded-For": "198.51.100.2"}
    )
    assert other_client.status_code == 200


# ---- 18. Storage failure fails closed --------------------------------------

def test_rate_limit_storage_failure_blocks_authentication(build, college, owner_engine):
    client = build()
    with owner_engine.begin() as conn:  # a genuine database error: the app role loses access
        conn.execute(text("REVOKE ALL ON rate_limit_buckets FROM opencampus_app"))
    try:
        response = login(client)
        register = client.post(
            "/api/auth/register",
            json={"email": "new@aldermoor.example", "password": "a long enough passphrase",
                  "full_name": "New", "institution_slug": "aldermoor"},
        )
    finally:
        with owner_engine.begin() as conn:
            conn.execute(text("GRANT SELECT, INSERT, UPDATE, DELETE ON rate_limit_buckets TO opencampus_app"))

    for r in (response, register):
        assert r.status_code == 503
        assert r.json() == {"detail": "Sign-in is temporarily unavailable. Please try again shortly.", "code": "rate_limit_unavailable"}
    assert count(AuthSession) == 0  # the login did not proceed
    assert count(User) == 2  # the registration did not proceed


# ---- 19. Keys reveal nothing ------------------------------------------------

def test_stored_keys_contain_no_raw_identifiers(build, college):
    client = build(ip="198.51.100.77")
    login(client, password=WRONG)
    with session_factory()() as db:
        keys = db.scalars(select(RateLimitBucket.key_hash)).all()
    assert keys and all(len(k) == 64 and int(k, 16) >= 0 for k in keys)
    joined = " ".join(keys)
    assert "maya" not in joined and "198.51.100.77" not in joined
