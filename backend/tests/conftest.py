"""Test setup: a dedicated Postgres database, migrated with Alembic.

Requires OPENCAMPUS_TEST_DATABASE_URL (runtime app role) and
OPENCAMPUS_TEST_MIGRATION_DATABASE_URL (owner role), e.g. from backend/.env.
The app connects as the non-owner role, so RLS is genuinely exercised.
"""

import os
import secrets

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
os.environ["OPENCAMPUS_ENV"] = "test"
os.environ["OPENCAMPUS_COOKIE_SECURE"] = "true"  # production-like cookies

from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine, text  # noqa: E402

from app.main import create_app  # noqa: E402

TABLES = "rate_limit_buckets, refresh_tokens, auth_sessions, memberships, users, institutions"


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
def app():
    return create_app()


@pytest.fixture
def make_client(app):
    """Each client has its own cookie jar, i.e. behaves like its own browser."""
    clients: list[TestClient] = []

    def factory() -> TestClient:
        client = TestClient(app, base_url="https://testserver")
        clients.append(client)
        return client

    yield factory
    for client in clients:
        client.close()


@pytest.fixture
def client(make_client):
    return make_client()
