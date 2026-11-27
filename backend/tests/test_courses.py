"""M4.1: courses and subjects."""

import uuid

import pytest
from sqlalchemy import create_engine, func, select, text
from sqlalchemy.exc import IntegrityError, ProgrammingError
from sqlalchemy.orm import Session

from app.db.session import session_factory, set_db_context
from app.models import Course, Subject
from tests.conftest import TEST_DATABASE_URL
from tests.helpers import course_body, create_course, create_subject, subject_body


# ---- CRUD -----------------------------------------------------------------


def test_admin_course_crud(college):
    admin = college["admin"]
    course = create_course(admin, code=" bsc-cs ", description="Three years")
    assert course["code"] == "BSC-CS" and course["status"] == "active" and course["duration_semesters"] == 6

    assert admin.get(f"/api/academic/courses/{course['id']}").json()["name"] == "B.Sc. Computer Science"
    assert [c["code"] for c in admin.get("/api/academic/courses").json()] == ["BSC-CS"]

    updated = admin.patch(f"/api/academic/courses/{course['id']}", {"name": "BSc CS", "description": None}).json()
    assert updated["name"] == "BSc CS" and updated["description"] is None and updated["code"] == "BSC-CS"


def test_admin_subject_crud(college):
    admin = college["admin"]
    course = create_course(admin)
    subject = create_subject(admin, course["id"], credits=3.5)
    assert subject["course_id"] == course["id"] and subject["credits"] == 3.5

    listed = admin.get(f"/api/academic/courses/{course['id']}/subjects").json()
    assert [s["code"] for s in listed] == ["CS101"]

    updated = admin.patch(f"/api/academic/subjects/{subject['id']}", {"semester": 2, "name": "Programming I"}).json()
    assert updated["semester"] == 2 and updated["name"] == "Programming I"
    assert admin.get(f"/api/academic/subjects/{subject['id']}").json()["semester"] == 2


def test_patch_rejects_null_for_required_fields_and_unknown_fields(college):
    admin = college["admin"]
    course = create_course(admin)
    assert admin.patch(f"/api/academic/courses/{course['id']}", {"name": None}).status_code == 422
    assert admin.patch(f"/api/academic/courses/{course['id']}", {"status": "archived"}).status_code == 422
    assert admin.patch(f"/api/academic/courses/{course['id']}", {"institution_id": str(uuid.uuid4())}).status_code == 422


def test_create_ignores_no_tenant_input(college):
    """institution_id is not an accepted field; the tenant comes from the session."""
    response = college["admin"].post(
        "/api/academic/courses", course_body(institution_id=str(college["halvard"].id))
    )
    assert response.status_code == 422


# ---- Archive --------------------------------------------------------------


def test_archive_and_restore(college):
    admin, student = college["admin"], college["student"]
    course = create_course(admin)
    subject = create_subject(admin, course["id"])

    assert admin.post(f"/api/academic/subjects/{subject['id']}/archive").json()["status"] == "archived"
    assert student.get(f"/api/academic/subjects/{subject['id']}").status_code == 404
    assert student.get(f"/api/academic/courses/{course['id']}/subjects").json() == []

    archived = admin.post(f"/api/academic/courses/{course['id']}/archive").json()
    assert archived["status"] == "archived"
    assert student.get("/api/academic/courses").json() == []
    assert student.get(f"/api/academic/courses/{course['id']}").status_code == 404
    # Admins still see archived records and can filter by status.
    assert [c["status"] for c in admin.get("/api/academic/courses?status=archived").json()] == ["archived"]
    # No new subjects on an archived course; subjects cannot be restored before it.
    blocked = admin.post(f"/api/academic/courses/{course['id']}/subjects", subject_body(code="CS102"))
    assert blocked.status_code == 409 and blocked.json()["code"] == "course_archived"
    assert admin.post(f"/api/academic/subjects/{subject['id']}/restore").json()["code"] == "course_archived"

    assert admin.post(f"/api/academic/courses/{course['id']}/restore").json()["status"] == "active"
    assert admin.post(f"/api/academic/subjects/{subject['id']}/restore").json()["status"] == "active"


def test_app_role_cannot_delete_academic_records(college):
    create_course(college["admin"])
    engine = create_engine(TEST_DATABASE_URL)
    try:
        with Session(engine) as db:
            set_db_context(db, tenant_id=college["aldermoor"].id)
            with pytest.raises(ProgrammingError, match="permission denied"):
                db.execute(text("DELETE FROM courses"))
    finally:
        engine.dispose()


# ---- Validation -----------------------------------------------------------


def test_course_code_unique_per_institution_case_insensitive(college):
    create_course(college["admin"], code="BSC-CS")
    duplicate = college["admin"].post("/api/academic/courses", course_body(code="bsc-cs"))
    assert duplicate.status_code == 409 and duplicate.json()["code"] == "course_code_taken"
    # Another institution may use the same code.
    create_course(college["other_admin"], code="BSC-CS")


def test_course_code_change_respects_uniqueness(college):
    admin = college["admin"]
    create_course(admin, code="A1")
    second = create_course(admin, code="B1")
    response = admin.patch(f"/api/academic/courses/{second['id']}", {"code": "a1"})
    assert response.status_code == 409 and response.json()["code"] == "course_code_taken"


def test_subject_code_unique_within_course(college):
    admin = college["admin"]
    first, second = create_course(admin, code="C1"), create_course(admin, code="C2")
    create_subject(admin, first["id"], code="CS101")
    duplicate = admin.post(f"/api/academic/courses/{first['id']}/subjects", subject_body(code="cs101"))
    assert duplicate.status_code == 409 and duplicate.json()["code"] == "subject_code_taken"
    create_subject(admin, second["id"], code="CS101")  # other course: allowed


@pytest.mark.parametrize(
    "body",
    [
        course_body(code="bad code"),
        course_body(code=""),
        course_body(duration_semesters=0),
        course_body(duration_semesters=21),
        course_body(degree_level="kindergarten"),
        course_body(name="   "),
    ],
)
def test_course_validation(college, body):
    assert college["admin"].post("/api/academic/courses", body).status_code == 422


@pytest.mark.parametrize(
    "overrides", [{"credits": 0}, {"credits": -1}, {"credits": 1.25}, {"semester": 0}, {"code": "has space"}]
)
def test_subject_validation(college, overrides):
    course = create_course(college["admin"])
    response = college["admin"].post(f"/api/academic/courses/{course['id']}/subjects", subject_body(**overrides))
    assert response.status_code == 422


def test_semester_must_be_within_course_duration(college):
    admin = college["admin"]
    course = create_course(admin, duration_semesters=4)
    over = admin.post(f"/api/academic/courses/{course['id']}/subjects", subject_body(semester=5))
    assert over.status_code == 409 and over.json()["code"] == "semester_out_of_range"

    subject = create_subject(admin, course["id"], semester=4)
    assert admin.patch(f"/api/academic/subjects/{subject['id']}", {"semester": 5}).json()["code"] == "semester_out_of_range"
    # The course cannot shrink below its subjects' semesters.
    shrink = admin.patch(f"/api/academic/courses/{course['id']}", {"duration_semesters": 3})
    assert shrink.status_code == 409 and shrink.json()["code"] == "duration_below_subjects"
    assert admin.patch(f"/api/academic/courses/{course['id']}", {"duration_semesters": 8}).status_code == 200


def test_database_rejects_non_positive_credits(college):
    course = create_course(college["admin"])
    with session_factory()() as db:
        set_db_context(db, tenant_id=college["aldermoor"].id)
        db.add(Subject(institution_id=college["aldermoor"].id, course_id=uuid.UUID(course["id"]), name="X", code="X1", semester=1, credits=0))
        with pytest.raises(IntegrityError, match="ck_subjects_credits_positive"):
            db.flush()


# ---- Roles ----------------------------------------------------------------


@pytest.mark.parametrize("role", ["student", "faculty"])
def test_students_and_faculty_read_but_cannot_write(college, role):
    admin, actor = college["admin"], college[role]
    course = create_course(admin)
    subject = create_subject(admin, course["id"])

    assert [c["id"] for c in actor.get("/api/academic/courses").json()] == [course["id"]]
    assert actor.get(f"/api/academic/courses/{course['id']}").status_code == 200
    assert [s["id"] for s in actor.get(f"/api/academic/courses/{course['id']}/subjects").json()] == [subject["id"]]
    assert actor.get(f"/api/academic/subjects/{subject['id']}").status_code == 200

    writes = [
        actor.post("/api/academic/courses", course_body(code="NEW")),
        actor.patch(f"/api/academic/courses/{course['id']}", {"name": "X"}),
        actor.post(f"/api/academic/courses/{course['id']}/archive"),
        actor.post(f"/api/academic/courses/{course['id']}/restore"),
        actor.post(f"/api/academic/courses/{course['id']}/subjects", subject_body(code="NEW")),
        actor.patch(f"/api/academic/subjects/{subject['id']}", {"name": "X"}),
        actor.post(f"/api/academic/subjects/{subject['id']}/archive"),
    ]
    assert [r.status_code for r in writes] == [403] * len(writes)
    assert all(r.json()["code"] == "insufficient_role" for r in writes)


def test_status_filter_is_ignored_for_non_admins(college):
    admin = college["admin"]
    course = create_course(admin)
    admin.post(f"/api/academic/courses/{course['id']}/archive")
    assert college["student"].get("/api/academic/courses?status=archived").json() == []


def test_requires_authentication_and_tenant(client, make_client):
    assert client.get("/api/academic/courses").status_code == 401
    # A platform admin without a membership has no tenant: academic data is not exposed.
    from tests.helpers import Actor, login, make_user

    make_user("root@platform.example", [], platform_admin=True)
    c = make_client()
    operator = Actor(c, login(c, "root@platform.example"), None)
    response = operator.get("/api/academic/courses")
    assert response.status_code == 403 and response.json()["code"] == "tenant_required"


# ---- Tenant isolation ------------------------------------------------------


def test_cross_institution_access_is_not_found(college):
    foreign = create_course(college["other_admin"], code="HAL-1")
    foreign_subject = create_subject(college["other_admin"], foreign["id"])
    admin = college["admin"]

    assert admin.get("/api/academic/courses").json() == []
    responses = [
        admin.get(f"/api/academic/courses/{foreign['id']}"),
        admin.patch(f"/api/academic/courses/{foreign['id']}", {"name": "Hijacked"}),
        admin.post(f"/api/academic/courses/{foreign['id']}/archive"),
        admin.get(f"/api/academic/courses/{foreign['id']}/subjects"),
        admin.post(f"/api/academic/courses/{foreign['id']}/subjects", subject_body(code="EVIL")),
        admin.get(f"/api/academic/subjects/{foreign_subject['id']}"),
        admin.patch(f"/api/academic/subjects/{foreign_subject['id']}", {"name": "Hijacked"}),
    ]
    assert [r.status_code for r in responses] == [404] * len(responses)
    assert college["other_admin"].get(f"/api/academic/courses/{foreign['id']}").json()["name"] != "Hijacked"


def test_database_rejects_subject_linked_to_other_institutions_course(college):
    """Composite FK: even with matching RLS context, a subject's course must be
    in the subject's own institution."""
    foreign = create_course(college["other_admin"], code="HAL-1")
    aldermoor = college["aldermoor"]
    with session_factory()() as db:
        set_db_context(db, tenant_id=aldermoor.id)
        db.add(Subject(institution_id=aldermoor.id, course_id=uuid.UUID(foreign["id"]), name="X", code="X1", semester=1, credits=1))
        with pytest.raises(IntegrityError, match="fk_subjects_course_same_institution"):
            db.flush()


def test_rls_isolates_courses_and_subjects(college):
    mine = create_course(college["admin"], code="ALD-1")
    create_subject(college["admin"], mine["id"])
    theirs = create_course(college["other_admin"], code="HAL-1")
    create_subject(college["other_admin"], theirs["id"])

    with session_factory()() as db:
        # Deliberately unfiltered queries: only RLS stands between tenants.
        set_db_context(db, tenant_id=college["aldermoor"].id)
        assert db.scalars(select(Course.code)).all() == ["ALD-1"]
        assert db.scalar(select(func.count()).select_from(Subject)) == 1
        # Writing a row for another tenant violates the policy.
        db.add(Course(institution_id=college["halvard"].id, name="X", code="X", degree_level="other", duration_semesters=1))
        with pytest.raises(ProgrammingError, match="row-level security"):
            db.flush()
        db.rollback()

        set_db_context(db, tenant_id=None)
        assert db.scalars(select(Course)).all() == []  # no context: fail closed
