"""Direct database setup for tests, using the same RLS-bound app role."""

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.config import get_settings
from app.core.security import hash_password
from app.db.session import session_factory, set_db_context
from app.models import Institution, Membership, MembershipRole, User

PASSWORD = "correct horse battery staple"
_HASH = None


def _password_hash() -> str:
    global _HASH
    if _HASH is None:
        _HASH = hash_password(PASSWORD)
    return _HASH


def make_institution(slug: str, name: str | None = None, open_registration: bool = True) -> Institution:
    with session_factory()() as db:
        institution = Institution(slug=slug, name=name or slug.title(), allow_self_registration=open_registration)
        db.add(institution)
        db.commit()
        return institution


def make_user(
    email: str,
    memberships: list[tuple[Institution, MembershipRole]] = (),
    *,
    name: str = "Test User",
    platform_admin: bool = False,
) -> User:
    with session_factory()() as db:
        user = User(email=email, full_name=name, password_hash=_password_hash(), is_platform_admin=platform_admin)
        db.add(user)
        db.flush()
        for institution, role in memberships:
            set_db_context(db, tenant_id=institution.id)
            db.add(Membership(institution_id=institution.id, user_id=user.id, role=role))
            db.flush()
        db.commit()
        return user


def membership_of(user: User, institution: Institution) -> Membership:
    with session_factory()() as db:
        set_db_context(db, tenant_id=institution.id)
        return db.scalar(
            select(Membership).where(Membership.user_id == user.id, Membership.institution_id == institution.id)
        )


def login(client: TestClient, email: str, password: str = PASSWORD, **extra) -> str:
    response = client.post("/api/auth/login", json={"email": email, "password": password, **extra})
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


def bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def csrf_headers(client: TestClient) -> dict[str, str]:
    return {"X-CSRF-Token": client.cookies.get(get_settings().csrf_cookie_name, "")}
