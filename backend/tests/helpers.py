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


class Actor:
    """A signed-in member: their own client (cookie jar) plus auth header."""

    def __init__(self, client: TestClient, token: str, user: User):
        self.client = client
        self.headers = bearer(token)
        self.user = user

    def get(self, path: str, **kwargs):
        return self.client.get(path, headers=self.headers, **kwargs)

    def post(self, path: str, json=None, **kwargs):
        return self.client.post(path, json=json, headers=self.headers, **kwargs)

    def patch(self, path: str, json=None, **kwargs):
        return self.client.patch(path, json=json, headers=self.headers, **kwargs)


_DEVICE = iter(range(1, 1_000_000))


def sign_in(make_client, email: str, memberships, *, name: str = "Test User", **extra) -> Actor:
    """Create a user and sign them in from their own device (distinct IP, so
    fixtures with many people stay under the per-IP login limit)."""
    user = make_user(email, memberships, name=name)
    n = next(_DEVICE)
    client = make_client(client_host=f"10.{n // 65536 % 256}.{n // 256 % 256}.{n % 256}")
    return Actor(client, login(client, email, **extra), user)


def course_body(code: str = "BSC-CS", **overrides) -> dict:
    return {
        "name": "B.Sc. Computer Science",
        "code": code,
        "degree_level": "bachelor",
        "duration_semesters": 6,
        **overrides,
    }


def subject_body(code: str = "CS101", **overrides) -> dict:
    return {"name": "Programming Fundamentals", "code": code, "semester": 1, "credits": 4, **overrides}


def create_course(actor: Actor, **overrides) -> dict:
    response = actor.post("/api/academic/courses", course_body(**overrides))
    assert response.status_code == 201, response.text
    return response.json()


def create_subject(actor: Actor, course_id: str, **overrides) -> dict:
    response = actor.post(f"/api/academic/courses/{course_id}/subjects", subject_body(**overrides))
    assert response.status_code == 201, response.text
    return response.json()


def enrol(actor: Actor, membership_id, course_id: str, *, year: str = "2026-27", period: str = "Semester 1") -> dict:
    response = actor.post(
        "/api/academic/enrolments",
        {"student_membership_id": str(membership_id), "course_id": course_id, "academic_year": year, "academic_period": period},
    )
    assert response.status_code == 201, response.text
    return response.json()
