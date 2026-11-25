"""Tenant isolation at the API layer and in PostgreSQL row-level security."""

import pytest
from sqlalchemy import create_engine, func, select, text, update
from sqlalchemy.exc import ProgrammingError
from sqlalchemy.orm import Session

from app.db.session import session_factory, set_db_context
from app.models import Institution, InstitutionStatus, Membership, MembershipRole
from tests.conftest import TEST_DATABASE_URL
from tests.helpers import bearer, login, make_institution, make_user, membership_of


@pytest.fixture
def two_colleges():
    aldermoor = make_institution("aldermoor", "Aldermoor College")
    halvard = make_institution("halvard", "Halvard Institute")
    make_user("admin@aldermoor.example", [(aldermoor, MembershipRole.college_admin)], name="Aldermoor Admin")
    make_user("maya@aldermoor.example", [(aldermoor, MembershipRole.student)], name="Maya Okafor")
    make_user("admin@halvard.example", [(halvard, MembershipRole.college_admin)], name="Halvard Admin")
    tomas = make_user("tomas@halvard.example", [(halvard, MembershipRole.student)], name="Tomas Berg")
    return aldermoor, halvard, tomas


# ---- API layer ------------------------------------------------------------

def test_admin_sees_only_own_institution_members(make_client, two_colleges):
    client = make_client()
    token = login(client, "admin@aldermoor.example")

    members = client.get("/api/institution/members", headers=bearer(token)).json()

    assert sorted(m["email"] for m in members) == ["admin@aldermoor.example", "maya@aldermoor.example"]


def test_admin_cannot_modify_other_institution_member(make_client, two_colleges):
    _, halvard, tomas = two_colleges
    client = make_client()
    token = login(client, "admin@aldermoor.example")
    foreign_membership = membership_of(tomas, halvard)

    response = client.patch(
        f"/api/institution/members/{foreign_membership.id}", json={"role": "faculty"}, headers=bearer(token)
    )

    assert response.status_code == 404  # indistinguishable from "does not exist"
    assert membership_of(tomas, halvard).role == MembershipRole.student


def test_cannot_log_in_or_switch_into_institution_without_membership(make_client, two_colleges):
    _, halvard, _ = two_colleges
    client = make_client()

    denied_login = client.post(
        "/api/auth/login",
        json={"email": "admin@aldermoor.example", "password": "correct horse battery staple", "institution_slug": "halvard"},
    )
    assert denied_login.status_code == 403 and denied_login.json()["code"] == "not_a_member"

    token = login(client, "admin@aldermoor.example")
    switch = client.post("/api/auth/switch-institution", json={"institution_id": str(halvard.id)}, headers=bearer(token))
    assert switch.status_code == 403
    # Still scoped to Aldermoor.
    assert client.get("/api/institution", headers=bearer(token)).json()["institution"]["slug"] == "aldermoor"


def test_tenant_cannot_be_chosen_by_request_parameters(make_client, two_colleges):
    _, halvard, _ = two_colleges
    client = make_client()
    token = login(client, "admin@aldermoor.example")

    response = client.get(
        "/api/institution/members",
        headers={**bearer(token), "X-Institution-Id": str(halvard.id)},
        params={"institution_id": str(halvard.id), "institution": "halvard"},
    )

    assert {m["email"] for m in response.json()} == {"admin@aldermoor.example", "maya@aldermoor.example"}


def test_multi_membership_switching_changes_tenant_and_role(make_client, two_colleges):
    aldermoor, halvard, _ = two_colleges
    make_user("sam@aldermoor.example", [(aldermoor, MembershipRole.college_admin), (halvard, MembershipRole.student)])
    client = make_client()
    token = login(client, "sam@aldermoor.example")

    me = client.get("/api/auth/me", headers=bearer(token)).json()
    assert len(me["memberships"]) == 2
    assert client.get("/api/institution/members", headers=bearer(token)).status_code == 200

    switched = client.post(
        "/api/auth/switch-institution", json={"institution_id": str(halvard.id)}, headers=bearer(token)
    )
    assert switched.status_code == 200
    assert switched.json()["active_institution"] == {
        "id": str(halvard.id), "slug": "halvard", "name": "Halvard Institute", "status": "active", "role": "student"
    }
    # Same token, new tenant: the role is now 'student', so admin access is gone.
    assert client.get("/api/institution/members", headers=bearer(token)).status_code == 403


def test_missing_tenant_context_fails_closed(make_client):
    make_user("ops@opencampus.example", platform_admin=True)  # no memberships at all
    client = make_client()
    token = login(client, "ops@opencampus.example")

    me = client.get("/api/auth/me", headers=bearer(token))
    assert me.status_code == 200 and me.json()["active_institution"] is None

    response = client.get("/api/institution", headers=bearer(token))
    assert response.status_code == 403
    assert response.json()["code"] == "tenant_required"


def test_suspended_institution_blocks_access(make_client, two_colleges):
    aldermoor, _, _ = two_colleges
    client = make_client()
    token = login(client, "maya@aldermoor.example")
    with session_factory()() as db:
        db.execute(update(Institution).where(Institution.id == aldermoor.id).values(status=InstitutionStatus.suspended))
        db.commit()

    response = client.get("/api/institution", headers=bearer(token))
    assert response.status_code == 403 and response.json()["code"] == "tenant_access_denied"


# ---- Database layer (RLS), connecting as the runtime app role ------------

def count_memberships(db: Session, *, where_institution=None) -> int:
    query = select(func.count()).select_from(Membership)
    if where_institution is not None:
        query = query.where(Membership.institution_id == where_institution)
    return db.scalar(query)


def test_rls_hides_all_rows_without_tenant_context(two_colleges):
    with session_factory()() as db:
        assert count_memberships(db) == 0


def test_rls_limits_unfiltered_queries_to_current_tenant(two_colleges):
    aldermoor, halvard, _ = two_colleges
    with session_factory()() as db:
        set_db_context(db, tenant_id=aldermoor.id)
        # No WHERE clause at all, yet only Aldermoor rows come back.
        assert count_memberships(db) == 2
        assert count_memberships(db, where_institution=halvard.id) == 0


def test_rls_blocks_writes_into_another_tenant(two_colleges):
    aldermoor, halvard, tomas = two_colleges
    with session_factory()() as db:
        set_db_context(db, tenant_id=aldermoor.id)
        db.add(Membership(institution_id=halvard.id, user_id=tomas.id, role=MembershipRole.college_admin))
        with pytest.raises(ProgrammingError, match="row-level security"):
            db.flush()


def test_rls_update_cannot_touch_other_tenant_rows(two_colleges):
    aldermoor, halvard, tomas = two_colleges
    with session_factory()() as db:
        set_db_context(db, tenant_id=aldermoor.id)
        result = db.execute(update(Membership).where(Membership.user_id == tomas.id).values(role=MembershipRole.faculty))
        assert result.rowcount == 0
        db.commit()
    assert membership_of(tomas, halvard).role == MembershipRole.student


def test_tenant_context_does_not_leak_across_pooled_connections(two_colleges):
    """set_config(..., is_local => true) ends with the transaction, so a
    connection returned to the pool carries no tenant into the next use."""
    aldermoor, _, _ = two_colleges
    engine = create_engine(TEST_DATABASE_URL, pool_size=1, max_overflow=0)
    try:
        with engine.connect() as conn:
            backend_pid = conn.execute(text("SELECT pg_backend_pid()")).scalar()
            conn.execute(text("SELECT set_config('app.tenant_id', :t, true)"), {"t": str(aldermoor.id)})
            assert conn.execute(text("SELECT count(*) FROM memberships")).scalar() == 2
            conn.commit()
            # Even on the same connection, the next transaction has no tenant.
            assert conn.execute(text("SELECT count(*) FROM memberships")).scalar() == 0
            conn.rollback()

        with engine.connect() as conn:  # same physical connection from the pool
            assert conn.execute(text("SELECT pg_backend_pid()")).scalar() == backend_pid
            assert conn.execute(text("SELECT count(*) FROM memberships")).scalar() == 0
    finally:
        engine.dispose()


def test_app_role_cannot_bypass_rls():
    engine = create_engine(TEST_DATABASE_URL)
    try:
        with engine.connect() as conn:
            row = conn.execute(
                text("SELECT rolsuper, rolbypassrls FROM pg_roles WHERE rolname = current_user")
            ).one()
            assert row == (False, False)
            forced = conn.execute(
                text("SELECT relrowsecurity, relforcerowsecurity FROM pg_class WHERE relname = 'memberships'")
            ).one()
            assert forced == (True, True)
    finally:
        engine.dispose()
