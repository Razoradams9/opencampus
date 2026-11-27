"""M4.2: student enrolments."""

import uuid

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError, ProgrammingError

from app.db.session import session_factory, set_db_context
from app.models import Enrolment
from tests.helpers import create_course, enrol


@pytest.fixture
def course(college):
    return create_course(college["admin"], code="BSC-CS")


def test_admin_enrols_student(college, course):
    enrolment = enrol(college["admin"], college["student"].membership_id, course["id"], period=" Semester   1 ")
    assert enrolment["status"] == "active"
    assert enrolment["academic_period"] == "Semester 1"
    assert enrolment["student"]["full_name"] == "Maya Okafor"
    assert enrolment["course"]["code"] == "BSC-CS"
    assert enrolment["completed_at"] is None and enrolment["withdrawn_at"] is None
    assert college["admin"].get(f"/api/academic/enrolments/{enrolment['id']}").json()["id"] == enrolment["id"]


@pytest.mark.parametrize("year", ["2026", "2026-28", "26-27", "2026/27"])
def test_academic_year_format(college, course, year):
    response = college["admin"].post(
        "/api/academic/enrolments",
        {"student_membership_id": str(college["student"].membership_id), "course_id": course["id"], "academic_year": year, "academic_period": "S1"},
    )
    assert response.status_code == 422


def test_duplicate_open_enrolment_rejected(college, course):
    admin, student = college["admin"], college["student"]
    first = enrol(admin, student.membership_id, course["id"])
    duplicate = admin.post(
        "/api/academic/enrolments",
        {"student_membership_id": str(student.membership_id), "course_id": course["id"], "academic_year": "2026-27", "academic_period": "Semester 1"},
    )
    assert duplicate.status_code == 409 and duplicate.json()["code"] == "enrolment_exists"

    # Suspended still counts as open.
    admin.patch(f"/api/academic/enrolments/{first['id']}", {"status": "suspended"})
    again = admin.post(
        "/api/academic/enrolments",
        {"student_membership_id": str(student.membership_id), "course_id": course["id"], "academic_year": "2026-27", "academic_period": "Semester 1"},
    )
    assert again.json()["code"] == "enrolment_exists"

    # Another period is a separate enrolment; after withdrawal the same period may be re-enrolled.
    enrol(admin, student.membership_id, course["id"], period="Semester 2")
    admin.patch(f"/api/academic/enrolments/{first['id']}", {"status": "withdrawn"})
    enrol(admin, student.membership_id, course["id"])
    history = admin.get(f"/api/academic/enrolments?student_membership_id={student.membership_id}").json()
    assert sorted(e["status"] for e in history) == ["active", "active", "withdrawn"]  # history preserved


def test_database_rejects_reopening_into_a_duplicate(college, course):
    """The partial unique index guards open rows even outside the API."""
    admin, student = college["admin"], college["student"]
    first = enrol(admin, student.membership_id, course["id"])
    admin.patch(f"/api/academic/enrolments/{first['id']}", {"status": "suspended"})
    # Bypass the API to create the conflicting row only possible after a status change.
    with session_factory()() as db:
        set_db_context(db, tenant_id=college["aldermoor"].id)
        db.execute(text("UPDATE enrolments SET status = 'withdrawn', withdrawn_at = now() WHERE id = :id"), {"id": first["id"]})
        db.commit()
    enrol(admin, student.membership_id, course["id"])
    with session_factory()() as db:
        set_db_context(db, tenant_id=college["aldermoor"].id)
        with pytest.raises(IntegrityError, match="uq_enrolments_open"):
            db.execute(text("UPDATE enrolments SET status = 'suspended', withdrawn_at = NULL WHERE id = :id"), {"id": first["id"]})


@pytest.mark.parametrize("role", ["admin", "faculty"])
def test_only_student_members_can_be_enrolled(college, course, role):
    response = college["admin"].post(
        "/api/academic/enrolments",
        {"student_membership_id": str(college[role].membership_id), "course_id": course["id"], "academic_year": "2026-27", "academic_period": "S1"},
    )
    assert response.status_code == 409 and response.json()["code"] == "not_an_active_student"


def test_suspended_student_cannot_be_enrolled_or_reactivated(college, course):
    admin, student = college["admin"], college["student"]
    enrolment = enrol(admin, student.membership_id, course["id"])
    admin.patch(f"/api/academic/enrolments/{enrolment['id']}", {"status": "suspended"})
    assert admin.patch(f"/api/institution/members/{student.membership_id}", {"status": "suspended"}).status_code == 200

    blocked = admin.post(
        "/api/academic/enrolments",
        {"student_membership_id": str(student.membership_id), "course_id": course["id"], "academic_year": "2027-28", "academic_period": "S1"},
    )
    assert blocked.json()["code"] == "not_an_active_student"
    reactivate = admin.patch(f"/api/academic/enrolments/{enrolment['id']}", {"status": "active"})
    assert reactivate.status_code == 409 and reactivate.json()["code"] == "not_an_active_student"


def test_unknown_or_archived_course(college, course):
    admin, student = college["admin"], college["student"]
    body = {"student_membership_id": str(student.membership_id), "academic_year": "2026-27", "academic_period": "S1"}
    assert admin.post("/api/academic/enrolments", {**body, "course_id": str(uuid.uuid4())}).status_code == 404
    admin.post(f"/api/academic/courses/{course['id']}/archive")
    archived = admin.post("/api/academic/enrolments", {**body, "course_id": course["id"]})
    assert archived.status_code == 409 and archived.json()["code"] == "course_archived"


def test_withdrawal_and_completion(college, course):
    admin = college["admin"]
    a = enrol(admin, college["student"].membership_id, course["id"])
    b = enrol(admin, college["student2"].membership_id, course["id"])

    withdrawn = admin.patch(f"/api/academic/enrolments/{a['id']}", {"status": "withdrawn"}).json()
    assert withdrawn["status"] == "withdrawn" and withdrawn["withdrawn_at"] is not None
    completed = admin.patch(f"/api/academic/enrolments/{b['id']}", {"status": "completed"}).json()
    assert completed["status"] == "completed" and completed["completed_at"] is not None

    # Terminal states cannot be reopened.
    for enrolment_id in (a["id"], b["id"]):
        response = admin.patch(f"/api/academic/enrolments/{enrolment_id}", {"status": "active"})
        assert response.status_code == 409 and response.json()["code"] == "invalid_status_transition"
    # Suspended -> completed is not allowed either.
    c = enrol(admin, college["student"].membership_id, course["id"], period="S2")
    admin.patch(f"/api/academic/enrolments/{c['id']}", {"status": "suspended"})
    assert admin.patch(f"/api/academic/enrolments/{c['id']}", {"status": "completed"}).json()["code"] == "invalid_status_transition"
    assert admin.patch(f"/api/academic/enrolments/{c['id']}", {"status": "active"}).json()["status"] == "active"


def test_patch_cannot_change_student_course_or_timestamps(college, course):
    admin = college["admin"]
    e = enrol(admin, college["student"].membership_id, course["id"])
    for body in ({"course_id": str(uuid.uuid4())}, {"student_membership_id": str(uuid.uuid4())}, {"status": "withdrawn", "withdrawn_at": "2020-01-01T00:00:00Z"}):
        assert admin.patch(f"/api/academic/enrolments/{e['id']}", body).status_code == 422


def test_database_requires_status_timestamps_to_agree(college, course):
    e = enrol(college["admin"], college["student"].membership_id, course["id"])
    with session_factory()() as db:
        set_db_context(db, tenant_id=college["aldermoor"].id)
        with pytest.raises(IntegrityError, match="ck_enrolments_completed_at_matches_status"):
            db.execute(text("UPDATE enrolments SET status = 'completed' WHERE id = :id"), {"id": e["id"]})


def test_no_physical_deletion(college, course):
    enrol(college["admin"], college["student"].membership_id, course["id"])
    with session_factory()() as db:
        set_db_context(db, tenant_id=college["aldermoor"].id)
        with pytest.raises(ProgrammingError, match="permission denied"):
            db.execute(text("DELETE FROM enrolments"))


# ---- Student self-access ---------------------------------------------------


def test_student_sees_only_own_enrolments(college, course):
    admin, student = college["admin"], college["student"]
    mine = enrol(admin, student.membership_id, course["id"])
    theirs = enrol(admin, college["student2"].membership_id, course["id"])

    assert [e["id"] for e in student.get("/api/academic/enrolments/me").json()] == [mine["id"]]
    assert [e["id"] for e in student.get("/api/academic/enrolments").json()] == [mine["id"]]
    # Filtering by someone else's membership does not widen the scope.
    assert student.get(f"/api/academic/enrolments?student_membership_id={college['student2'].membership_id}").json() == []
    assert student.get(f"/api/academic/enrolments/{mine['id']}").status_code == 200
    assert student.get(f"/api/academic/enrolments/{theirs['id']}").status_code == 404
    assert student.get(f"/api/academic/courses/{course['id']}/enrolments").status_code == 403


def test_student_cannot_enrol_or_change_status(college, course):
    student = college["student"]
    response = student.post(
        "/api/academic/enrolments",
        {"student_membership_id": str(student.membership_id), "course_id": course["id"], "academic_year": "2026-27", "academic_period": "S1"},
    )
    assert response.status_code == 403
    e = enrol(college["admin"], student.membership_id, course["id"])
    assert student.patch(f"/api/academic/enrolments/{e['id']}", {"status": "completed"}).status_code == 403
    assert student.get("/api/academic/enrolments/me").json()[0]["status"] == "active"


def test_faculty_without_assignment_has_no_enrolment_access(college, course):
    e = enrol(college["admin"], college["student"].membership_id, course["id"])
    faculty = college["faculty"]
    # Scoped by teaching assignments (M4.3): with none, nothing is visible.
    assert faculty.get("/api/academic/enrolments").json() == []
    assert faculty.get(f"/api/academic/enrolments/{e['id']}").status_code == 404
    roster = faculty.get(f"/api/academic/courses/{course['id']}/enrolments")
    assert roster.status_code == 403 and roster.json()["code"] == "not_assigned"
    assert faculty.get("/api/academic/enrolments/me").json() == []


# ---- Admin -----------------------------------------------------------------


def test_admin_roster_and_filters(college, course):
    admin = college["admin"]
    other = create_course(admin, code="BA-ENG", degree_level="bachelor")
    enrol(admin, college["student"].membership_id, course["id"])
    enrol(admin, college["student2"].membership_id, course["id"])
    enrol(admin, college["student"].membership_id, other["id"], year="2025-26")

    roster = admin.get(f"/api/academic/courses/{course['id']}/enrolments").json()
    assert [e["student"]["full_name"] for e in roster] == ["Maya Okafor", "Ravi Shah"]
    assert len(admin.get("/api/academic/enrolments?academic_year=2025-26").json()) == 1
    assert len(admin.get(f"/api/academic/enrolments?course_id={other['id']}").json()) == 1
    assert len(admin.get("/api/academic/enrolments?limit=2").json()) == 2
    assert len(admin.get("/api/academic/enrolments?limit=2&offset=2").json()) == 1
    assert admin.get(f"/api/academic/courses/{uuid.uuid4()}/enrolments").status_code == 404


# ---- Tenant isolation ------------------------------------------------------


def test_cannot_enrol_other_institutions_student_or_course(college, course):
    admin = college["admin"]
    foreign_course = create_course(college["other_admin"], code="HAL-1")
    body = {"academic_year": "2026-27", "academic_period": "S1"}
    foreign_student = admin.post(
        "/api/academic/enrolments", {**body, "student_membership_id": str(college["other_student"].membership_id), "course_id": course["id"]}
    )
    assert foreign_student.status_code == 404 and foreign_student.json()["code"] == "student_not_found"
    foreign = admin.post(
        "/api/academic/enrolments", {**body, "student_membership_id": str(college["student"].membership_id), "course_id": foreign_course["id"]}
    )
    assert foreign.status_code == 404 and foreign.json()["code"] == "course_not_found"


def test_other_institution_cannot_read_or_modify_enrolments(college, course):
    e = enrol(college["admin"], college["student"].membership_id, course["id"])
    other = college["other_admin"]
    assert other.get("/api/academic/enrolments").json() == []
    assert other.get(f"/api/academic/enrolments/{e['id']}").status_code == 404
    assert other.patch(f"/api/academic/enrolments/{e['id']}", {"status": "withdrawn"}).status_code == 404
    assert other.get(f"/api/academic/courses/{course['id']}/enrolments").status_code == 404
    assert college["admin"].get(f"/api/academic/enrolments/{e['id']}").json()["status"] == "active"


def test_database_rejects_cross_institution_enrolment(college, course):
    """Composite FKs hold even if the service checks were bypassed."""
    aldermoor = college["aldermoor"]
    with session_factory()() as db:
        set_db_context(db, tenant_id=aldermoor.id)
        db.add(Enrolment(institution_id=aldermoor.id, student_membership_id=college["other_student"].membership_id, course_id=uuid.UUID(course["id"]), academic_year="2026-27", academic_period="S1"))
        with pytest.raises(IntegrityError, match="fk_enrolments_membership_same_institution"):
            db.flush()


def test_rls_isolates_enrolments(college, course):
    enrol(college["admin"], college["student"].membership_id, course["id"])
    foreign_course = create_course(college["other_admin"], code="HAL-1")
    enrol(college["other_admin"], college["other_student"].membership_id, foreign_course["id"])
    with session_factory()() as db:
        set_db_context(db, tenant_id=college["aldermoor"].id)
        assert db.scalar(select(func.count()).select_from(Enrolment)) == 1
        set_db_context(db, tenant_id=college["halvard"].id)
        assert db.scalar(select(func.count()).select_from(Enrolment)) == 1
        set_db_context(db, tenant_id=None)
        assert db.scalar(select(func.count()).select_from(Enrolment)) == 0
        set_db_context(db, tenant_id=college["aldermoor"].id)
        db.add(Enrolment(institution_id=college["halvard"].id, student_membership_id=college["other_student"].membership_id, course_id=uuid.UUID(foreign_course["id"]), academic_year="2027-28", academic_period="S1"))
        with pytest.raises(ProgrammingError, match="row-level security"):
            db.flush()
