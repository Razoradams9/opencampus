from app.models import MembershipRole
from tests.helpers import bearer, login, make_institution, make_user, membership_of


def test_member_listing_is_college_admin_only(make_client):
    aldermoor = make_institution("aldermoor")
    make_user("student@aldermoor.example", [(aldermoor, MembershipRole.student)])
    make_user("faculty@aldermoor.example", [(aldermoor, MembershipRole.faculty)])
    make_user("admin@aldermoor.example", [(aldermoor, MembershipRole.college_admin)])

    for email, expected in [
        ("student@aldermoor.example", 403),
        ("faculty@aldermoor.example", 403),
        ("admin@aldermoor.example", 200),
    ]:
        client = make_client()
        response = client.get("/api/institution/members", headers=bearer(login(client, email)))
        assert response.status_code == expected, email
        if expected == 403:
            assert response.json()["code"] == "insufficient_role"


def test_role_comes_from_database_not_from_client(make_client):
    """A client cannot claim a role: there is no role claim in the token,
    and request bodies/headers carrying one are ignored or rejected."""
    aldermoor = make_institution("aldermoor")
    make_user("student@aldermoor.example", [(aldermoor, MembershipRole.student)])
    client = make_client()
    token = login(client, "student@aldermoor.example")

    response = client.get(
        "/api/institution/members", headers={**bearer(token), "X-Role": "college_admin"}, params={"role": "college_admin"}
    )
    assert response.status_code == 403


def test_role_change_takes_effect_without_new_token(make_client):
    aldermoor = make_institution("aldermoor")
    admin = make_user("admin@aldermoor.example", [(aldermoor, MembershipRole.college_admin)])
    student = make_user("student@aldermoor.example", [(aldermoor, MembershipRole.student)])
    admin_client, student_client = make_client(), make_client()
    admin_token = login(admin_client, "admin@aldermoor.example")
    student_token = login(student_client, "student@aldermoor.example")
    membership = membership_of(student, aldermoor)

    promoted = admin_client.patch(
        f"/api/institution/members/{membership.id}", json={"role": "faculty"}, headers=bearer(admin_token)
    )
    assert promoted.status_code == 200 and promoted.json()["role"] == "faculty"
    me = student_client.get("/api/auth/me", headers=bearer(student_token)).json()
    assert me["active_institution"]["role"] == "faculty"

    suspended = admin_client.patch(
        f"/api/institution/members/{membership.id}", json={"status": "suspended"}, headers=bearer(admin_token)
    )
    assert suspended.status_code == 200
    blocked = student_client.get("/api/institution", headers=bearer(student_token))
    assert blocked.status_code == 403 and blocked.json()["code"] == "tenant_access_denied"
    assert admin.id  # admin unaffected


def test_college_admin_cannot_grant_admin_or_modify_admins(make_client):
    aldermoor = make_institution("aldermoor")
    admin = make_user("admin@aldermoor.example", [(aldermoor, MembershipRole.college_admin)])
    other_admin = make_user("admin2@aldermoor.example", [(aldermoor, MembershipRole.college_admin)])
    student = make_user("student@aldermoor.example", [(aldermoor, MembershipRole.student)])
    client = make_client()
    token = login(client, "admin@aldermoor.example")

    grant = client.patch(
        f"/api/institution/members/{membership_of(student, aldermoor).id}",
        json={"role": "college_admin"},
        headers=bearer(token),
    )
    demote_peer = client.patch(
        f"/api/institution/members/{membership_of(other_admin, aldermoor).id}",
        json={"role": "student"},
        headers=bearer(token),
    )
    demote_self = client.patch(
        f"/api/institution/members/{membership_of(admin, aldermoor).id}", json={"role": "student"}, headers=bearer(token)
    )

    assert grant.status_code == 422
    assert demote_peer.status_code == 403
    assert demote_self.status_code == 403


def test_platform_endpoints_require_platform_admin(make_client):
    aldermoor = make_institution("aldermoor")
    make_user("admin@aldermoor.example", [(aldermoor, MembershipRole.college_admin)])
    client = make_client()
    token = login(client, "admin@aldermoor.example")

    response = client.post("/api/platform/institutions", json={"slug": "rogue", "name": "Rogue"}, headers=bearer(token))
    assert response.status_code == 403
    assert response.json()["code"] == "platform_admin_required"
    assert client.post("/api/platform/institutions", json={"slug": "rogue", "name": "Rogue"}).status_code == 401


def test_platform_admin_creates_institution_and_provisions_admin(make_client):
    make_user("ops@opencampus.example", platform_admin=True)
    future_admin = make_user("iris@halvard.example", name="Iris Moreau")
    ops = make_client()
    token = login(ops, "ops@opencampus.example")

    created = ops.post(
        "/api/platform/institutions", json={"slug": "halvard", "name": "Halvard Institute"}, headers=bearer(token)
    )
    assert created.status_code == 201
    assert created.json()["allow_self_registration"] is False  # closed by default
    assert ops.post(
        "/api/platform/institutions", json={"slug": "halvard", "name": "Dup"}, headers=bearer(token)
    ).status_code == 409

    provisioned = ops.post(
        "/api/platform/institutions/halvard/admins", json={"email": "iris@halvard.example"}, headers=bearer(token)
    )
    assert provisioned.status_code == 201
    assert provisioned.json()["role"] == "college_admin"
    assert provisioned.json()["user_id"] == str(future_admin.id)

    iris = make_client()
    iris_token = login(iris, "iris@halvard.example")
    assert iris.get("/api/institution/members", headers=bearer(iris_token)).status_code == 200


def test_institution_lookup_by_slug_and_status(make_client):
    make_institution("aldermoor", "Aldermoor College")
    make_user("ops@opencampus.example", platform_admin=True)
    client = make_client()

    found = client.get("/api/institutions/aldermoor")
    assert found.status_code == 200
    assert found.json() == {"slug": "aldermoor", "name": "Aldermoor College", "status": "active", "registration_open": True}
    assert client.get("/api/institutions/missing").status_code == 404

    token = login(client, "ops@opencampus.example")
    suspended = client.patch(
        "/api/platform/institutions/aldermoor", json={"status": "suspended"}, headers=bearer(token)
    )
    assert suspended.status_code == 200
    after = client.get("/api/institutions/aldermoor").json()
    assert after["status"] == "suspended" and after["registration_open"] is False
