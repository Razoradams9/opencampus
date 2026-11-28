"""Test setup: a dedicated Postgres database, migrated with Alembic.

Requires OPENCAMPUS_TEST_DATABASE_URL (runtime app role) and
OPENCAMPUS_TEST_MIGRATION_DATABASE_URL (owner role), e.g. from backend/.env.
The app connects as the non-owner role, so RLS is genuinely exercised.
"""

import os
import secrets
import tempfile
import time

import pytest

from app.core.config import load_env_file

load_env_file()
TEST_DATABASE_URL = os.getenv("OPENCAMPUS_TEST_DATABASE_URL")
TEST_MIGRATION_URL = os.getenv("OPENCAMPUS_TEST_MIGRATION_DATABASE_URL")
if not TEST_DATABASE_URL or not TEST_MIGRATION_URL:
    raise pytest.UsageError(
        "Set OPENCAMPUS_TEST_DATABASE_URL and OPENCAMPUS_TEST_MIGRATION_DATABASE_URL (see backend/.env.example)"
    )
if "test" not in TEST_DATABASE_URL.rsplit("/", 1)[-1]:
    raise pytest.UsageError("Refusing to run: test database name must contain 'test'")

# Override (not setdefault) so tests can never touch the development database.
os.environ["OPENCAMPUS_DATABASE_URL"] = TEST_DATABASE_URL
os.environ["OPENCAMPUS_JWT_SECRET"] = secrets.token_urlsafe(48)  # fresh per run, never hardcoded
os.environ["OPENCAMPUS_RATE_LIMIT_SECRET"] = secrets.token_urlsafe(48)
os.environ.pop("OPENCAMPUS_TRUSTED_PROXIES", None)  # tests set proxies explicitly where needed
# Email: always the development sink in a throwaway directory; never real SMTP.
for _name in [n for n in os.environ if n.startswith("OPENCAMPUS_SMTP_")]:
    os.environ.pop(_name)
os.environ["OPENCAMPUS_EMAIL_MODE"] = "dev_file"
os.environ["OPENCAMPUS_EMAIL_DEV_DIR"] = tempfile.mkdtemp(prefix="opencampus-test-mail-")
os.environ["OPENCAMPUS_FRONTEND_URL"] = "http://localhost:5173"
os.environ["OPENCAMPUS_ENV"] = "test"
os.environ["OPENCAMPUS_COOKIE_SECURE"] = "true"  # production-like cookies

from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine, text  # noqa: E402

from app.main import create_app  # noqa: E402

TABLES = "learning_resources, class_sessions, faculty_assignments, rooms, enrolments, subjects, courses, password_reset_tokens, rate_limit_buckets, refresh_tokens, auth_sessions, memberships, users, institutions"


@pytest.fixture(scope="session")
def owner_engine():
    config = Config(os.path.join(os.path.dirname(__file__), "..", "alembic.ini"))
    config.attributes["url"] = TEST_MIGRATION_URL
    command.downgrade(config, "base")
    command.upgrade(config, "head")
    engine = create_engine(TEST_MIGRATION_URL)
    yield engine
    engine.dispose()


@pytest.fixture(autouse=True)
def clean_db(owner_engine):
    with owner_engine.begin() as conn:
        conn.execute(text(f"TRUNCATE {TABLES} CASCADE"))
    yield


@pytest.fixture
def clear_of_window_edge(owner_engine):
    """Rate-limit windows are aligned to whole minutes of *database* time. A
    test that straddles a boundary would see its counters reset mid-test, so
    start only when at least 10 s remain in the current minute. (Every 15-min
    and hourly boundary is also a minute boundary.)"""
    with owner_engine.connect() as conn:
        seconds = conn.execute(text("SELECT extract(second FROM clock_timestamp())::float8")).scalar_one()
    if seconds > 50:
        time.sleep(60 - seconds + 0.2)


@pytest.fixture
def app():
    return create_app()


@pytest.fixture
def make_client(app):
    """Each client has its own cookie jar, i.e. behaves like its own browser."""
    clients: list[TestClient] = []

    def factory(client_host: str = "testclient") -> TestClient:
        # A distinct client_host models a separate device (own IP for rate limits).
        client = TestClient(app, base_url="https://testserver", client=(client_host, 50000))
        clients.append(client)
        return client

    yield factory
    for client in clients:
        client.close()


@pytest.fixture
def client(make_client):
    return make_client()


@pytest.fixture
def college(make_client):
    """Two institutions with signed-in members: Aldermoor (admin, faculty, two
    students) and Halvard (admin, student)."""
    from app.models import MembershipRole
    from tests.helpers import make_institution, membership_of, sign_in

    aldermoor = make_institution("aldermoor", "Aldermoor College")
    halvard = make_institution("halvard", "Halvard Institute")
    people = {
        "admin": ("admin@aldermoor.example", aldermoor, MembershipRole.college_admin, "Aldermoor Admin"),
        "faculty": ("prof@aldermoor.example", aldermoor, MembershipRole.faculty, "Ada Prof"),
        "student": ("maya@aldermoor.example", aldermoor, MembershipRole.student, "Maya Okafor"),
        "student2": ("ravi@aldermoor.example", aldermoor, MembershipRole.student, "Ravi Shah"),
        "other_admin": ("admin@halvard.example", halvard, MembershipRole.college_admin, "Halvard Admin"),
        "other_student": ("tomas@halvard.example", halvard, MembershipRole.student, "Tomas Berg"),
    }
    result = {"aldermoor": aldermoor, "halvard": halvard}
    for key, (email, institution, role, name) in people.items():
        actor = sign_in(make_client, email, [(institution, role)], name=name)
        actor.membership_id = membership_of(actor.user, institution).id
        result[key] = actor
    return result


@pytest.fixture
def teaching(college, make_client):
    """Aldermoor BSC-CS with CS101 (taught by `faculty`) and CS102 (taught by
    `faculty2`); `student` is actively enrolled, `student2` is not. Halvard
    has its own course and subject H101 taught by nobody."""
    from app.models import MembershipRole
    from tests.helpers import assign_faculty, create_course, create_subject, enrol, membership_of, sign_in

    admin = college["admin"]
    course = create_course(admin, code="BSC-CS")
    cs101 = create_subject(admin, course["id"], code="CS101")
    cs102 = create_subject(admin, course["id"], code="CS102", name="Discrete Maths")
    faculty2 = sign_in(make_client, "lin@aldermoor.example", [(college["aldermoor"], MembershipRole.faculty)], name="Lin Chen")
    faculty2.membership_id = membership_of(faculty2.user, college["aldermoor"]).id
    assign_faculty(admin, cs101["id"], college["faculty"].membership_id)
    assign_faculty(admin, cs102["id"], faculty2.membership_id)
    enrol(admin, college["student"].membership_id, course["id"])
    other_course = create_course(college["other_admin"], code="HAL-1")
    h101 = create_subject(college["other_admin"], other_course["id"], code="H101")
    return {**college, "course": course, "cs101": cs101, "cs102": cs102, "faculty2": faculty2, "h101": h101}
