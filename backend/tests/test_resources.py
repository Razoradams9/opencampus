"""M4.4: learning resources and notes."""

import uuid

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError, ProgrammingError

from app.db.session import session_factory, set_db_context
from app.models import LearningResource

NOTE = {"title": "Week 1 notes", "resource_type": "note", "body": "Variables and types.", "topic": "Week 1"}
LINK = {"title": "Python docs", "resource_type": "link", "external_url": "https://docs.python.org/3/"}


def make(actor, subject_id, body=NOTE, publish=False) -> dict:
    r = actor.post(f"/api/academic/subjects/{subject_id}/resources", body)
    assert r.status_code == 201, r.text
    if publish:
        r = actor.post(f"/api/academic/resources/{r.json()['id']}/publish")
        assert r.status_code == 200, r.text
    return r.json()


# ---- Create / read ----------------------------------------------------------


def test_faculty_creates_and_reads_resources(teaching):
    faculty = teaching["faculty"]
    note = make(faculty, teaching["cs101"]["id"])
    assert note["status"] == "draft" and note["published_at"] is None and note["file_available"] is False
    assert note["subject"]["code"] == "CS101" and note["course"]["code"] == "BSC-CS"
    assert note["created_by"]["full_name"] == "Ada Prof" and "email" not in note["created_by"]
    link = make(faculty, teaching["cs101"]["id"], {**LINK, "description": "Official reference"})
    assert link["external_url"] == "https://docs.python.org/3/"
    assert faculty.get(f"/api/academic/resources/{note['id']}").json()["body"] == "Variables and types."
    listed = faculty.get(f"/api/academic/subjects/{teaching['cs101']['id']}/resources").json()
    assert {r["id"] for r in listed} == {note["id"], link["id"]}


def test_update_publish_archive_lifecycle(teaching):
    faculty, student = teaching["faculty"], teaching["student"]
    r = make(faculty, teaching["cs101"]["id"])
    updated = faculty.patch(f"/api/academic/resources/{r['id']}", {"title": "Week 1: basics", "topic": None}).json()
    assert updated["title"] == "Week 1: basics" and updated["topic"] is None

    published = faculty.post(f"/api/academic/resources/{r['id']}/publish").json()
    assert published["status"] == "published" and published["published_at"]
    assert student.get(f"/api/academic/resources/{r['id']}").status_code == 200
    # Editing a published resource is allowed; republishing keeps the first timestamp.
    faculty.patch(f"/api/academic/resources/{r['id']}", {"body": "Updated."})
    assert faculty.post(f"/api/academic/resources/{r['id']}/publish").json()["published_at"] == published["published_at"]

    archived = faculty.post(f"/api/academic/resources/{r['id']}/archive").json()
    assert archived["status"] == "archived" and archived["published_at"] == published["published_at"]
    assert student.get(f"/api/academic/resources/{r['id']}").status_code == 404
    assert faculty.patch(f"/api/academic/resources/{r['id']}", {"title": "x"}).json()["code"] == "resource_archived"
    assert faculty.post(f"/api/academic/resources/{r['id']}/publish").json()["code"] == "resource_archived"
    # Preserved, still visible to its managers.
    assert faculty.get(f"/api/academic/resources/{r['id']}").json()["status"] == "archived"


def test_archiving_a_draft_never_publishes_it(teaching):
    r = make(teaching["faculty"], teaching["cs101"]["id"])
    archived = teaching["faculty"].post(f"/api/academic/resources/{r['id']}/archive").json()
    assert archived["status"] == "archived" and archived["published_at"] is None


# ---- Validation -------------------------------------------------------------


@pytest.mark.parametrize(
    "body",
    [
        {"title": "x", "resource_type": "spreadsheet", "external_url": "https://a.example"},
        {"title": "x", "resource_type": "note"},
        {"title": "x", "resource_type": "note", "body": "   "},
        {"title": "x", "resource_type": "note", "body": "hi", "external_url": "https://a.example"},
        {"title": "x", "resource_type": "link"},
        {"title": "x", "resource_type": "pdf"},  # no storage: a PDF needs a link
        {"title": "x", "resource_type": "link", "external_url": "javascript:alert(1)"},
        {"title": "x", "resource_type": "link", "external_url": "ftp://files.example/a"},
        {"title": "x", "resource_type": "link", "external_url": "https://"},
        {"title": "x", "resource_type": "link", "external_url": "https://a.example/with space"},
        {"title": "x", "resource_type": "video", "external_url": "data:text/html,hi"},
        {"title": " ", "resource_type": "note", "body": "hi"},
        {**NOTE, "storage_key": "uploads/x.pdf"},
        {**NOTE, "institution_id": str(uuid.uuid4())},
        {**NOTE, "created_by_membership_id": str(uuid.uuid4())},
    ],
)
def test_invalid_resources_rejected(teaching, body):
    r = teaching["faculty"].post(f"/api/academic/subjects/{teaching['cs101']['id']}/resources", body)
    assert r.status_code == 422, r.text


def test_update_validates_the_merged_result(teaching):
    faculty = teaching["faculty"]
    note = make(faculty, teaching["cs101"]["id"])
    # Turning a note into a link without giving a URL leaves invalid content.
    r = faculty.patch(f"/api/academic/resources/{note['id']}", {"resource_type": "link"})
    assert r.status_code == 422 and r.json()["code"] == "invalid_resource_content"
    ok = faculty.patch(f"/api/academic/resources/{note['id']}", {"resource_type": "link", "body": None, "external_url": "https://x.example/a"})
    assert ok.status_code == 200 and ok.json()["resource_type"] == "link"


def test_pdf_by_url_and_database_content_check(teaching):
    pdf = make(teaching["faculty"], teaching["cs101"]["id"], {"title": "Syllabus", "resource_type": "pdf", "external_url": "https://x.example/s.pdf"})
    assert pdf["resource_type"] == "pdf" and pdf["file_available"] is False
    with session_factory()() as db:
        set_db_context(db, tenant_id=teaching["aldermoor"].id)
        with pytest.raises(IntegrityError, match="ck_learning_resources_content"):
            db.execute(text("UPDATE learning_resources SET external_url = NULL WHERE id = :id"), {"id": pdf["id"]})


def test_cannot_add_to_archived_subject(teaching):
    teaching["admin"].post(f"/api/academic/subjects/{teaching['cs101']['id']}/archive")
    r = teaching["faculty"].post(f"/api/academic/subjects/{teaching['cs101']['id']}/resources", NOTE)
    assert r.status_code == 409 and r.json()["code"] == "subject_archived"


# ---- Visibility -------------------------------------------------------------


def test_student_sees_only_published_resources_of_enrolled_courses(teaching):
    faculty, student = teaching["faculty"], teaching["student"]
    draft = make(faculty, teaching["cs101"]["id"], {**NOTE, "title": "Draft"})
    live = make(faculty, teaching["cs101"]["id"], LINK, publish=True)
    other = make(teaching["faculty2"], teaching["cs102"]["id"], {**NOTE, "title": "CS102 notes"}, publish=True)

    assert {r["id"] for r in student.get("/api/academic/resources/me").json()} == {live["id"], other["id"]}
    assert [r["id"] for r in student.get(f"/api/academic/resources/me?subject_id={teaching['cs101']['id']}").json()] == [live["id"]]
    assert [r["id"] for r in student.get(f"/api/academic/subjects/{teaching['cs101']['id']}/resources").json()] == [live["id"]]
    assert student.get(f"/api/academic/resources/{draft['id']}").status_code == 404
    # A status filter cannot reveal drafts.
    assert student.get(f"/api/academic/subjects/{teaching['cs101']['id']}/resources?status=draft").json() == []


def test_unenrolled_or_withdrawn_student_sees_nothing(teaching):
    admin, student = teaching["admin"], teaching["student"]
    live = make(teaching["faculty"], teaching["cs101"]["id"], LINK, publish=True)
    outsider = teaching["student2"]
    assert outsider.get("/api/academic/resources/me").json() == []
    assert outsider.get(f"/api/academic/resources/{live['id']}").status_code == 404
    r = outsider.get(f"/api/academic/subjects/{teaching['cs101']['id']}/resources")
    assert r.status_code == 403 and r.json()["code"] == "not_enrolled_or_assigned"

    enrolment = student.get("/api/academic/enrolments/me").json()[0]
    admin.patch(f"/api/academic/enrolments/{enrolment['id']}", {"status": "withdrawn"})
    assert student.get("/api/academic/resources/me").json() == []
    assert student.get(f"/api/academic/resources/{live['id']}").status_code == 404


def test_students_cannot_write(teaching):
    student = teaching["student"]
    live = make(teaching["faculty"], teaching["cs101"]["id"], LINK, publish=True)
    assert student.post(f"/api/academic/subjects/{teaching['cs101']['id']}/resources", NOTE).status_code == 403
    for r in (
        student.patch(f"/api/academic/resources/{live['id']}", {"title": "x"}),
        student.post(f"/api/academic/resources/{live['id']}/archive"),
    ):
        assert r.status_code == 403
    assert student.get("/api/academic/resources/managed").status_code == 403


# ---- Faculty permissions ----------------------------------------------------


def test_faculty_manage_only_subjects_they_teach(teaching):
    faculty, other = teaching["faculty"], teaching["faculty2"]
    mine = make(faculty, teaching["cs101"]["id"])
    theirs = make(other, teaching["cs102"]["id"])

    r = faculty.post(f"/api/academic/subjects/{teaching['cs102']['id']}/resources", NOTE)
    assert r.status_code == 403 and r.json()["code"] == "not_assigned"
    assert faculty.patch(f"/api/academic/resources/{theirs['id']}", {"title": "x"}).json()["code"] == "not_assigned"
    assert faculty.post(f"/api/academic/resources/{theirs['id']}/publish").status_code == 403
    # Not even their drafts are readable.
    assert faculty.get(f"/api/academic/resources/{theirs['id']}").status_code == 404
    assert faculty.get(f"/api/academic/subjects/{teaching['cs102']['id']}/resources").status_code == 403
    assert [r["id"] for r in faculty.get("/api/academic/resources/managed").json()] == [mine["id"]]


def test_ending_assignment_revokes_management(teaching):
    admin, faculty = teaching["admin"], teaching["faculty"]
    r = make(faculty, teaching["cs101"]["id"])
    assignment = faculty.get("/api/academic/faculty-assignments/me").json()[0]
    admin.post(f"/api/academic/faculty-assignments/{assignment['id']}/end")
    assert faculty.patch(f"/api/academic/resources/{r['id']}", {"title": "x"}).status_code == 403
    assert faculty.get("/api/academic/resources/managed").json() == []


def test_admin_manages_everything(teaching):
    admin = teaching["admin"]
    r = make(admin, teaching["cs102"]["id"], LINK)
    assert r["created_by"]["full_name"] == "Aldermoor Admin"
    make(teaching["faculty"], teaching["cs101"]["id"])
    assert len(admin.get("/api/academic/resources/managed").json()) == 2
    assert len(admin.get("/api/academic/resources/managed?status=draft").json()) == 2
    assert admin.post(f"/api/academic/resources/{r['id']}/publish").json()["status"] == "published"


# ---- Tenant isolation -------------------------------------------------------


def test_cross_institution_access_denied(teaching):
    mine = make(teaching["faculty"], teaching["cs101"]["id"], LINK, publish=True)
    other = teaching["other_admin"]
    theirs = make(other, teaching["h101"]["id"], NOTE, publish=True)
    assert [r["id"] for r in other.get("/api/academic/resources/managed").json()] == [theirs["id"]]
    checks = [
        other.get(f"/api/academic/resources/{mine['id']}"),
        other.patch(f"/api/academic/resources/{mine['id']}", {"title": "x"}),
        other.post(f"/api/academic/resources/{mine['id']}/archive"),
        other.get(f"/api/academic/subjects/{teaching['cs101']['id']}/resources"),
        other.post(f"/api/academic/subjects/{teaching['cs101']['id']}/resources", NOTE),
        teaching["admin"].get(f"/api/academic/resources/{theirs['id']}"),
        teaching["admin"].post(f"/api/academic/subjects/{teaching['h101']['id']}/resources", NOTE),
    ]
    assert [r.status_code for r in checks] == [404] * len(checks)
    assert teaching["other_student"].get("/api/academic/resources/me").json() == []


def test_database_rejects_cross_institution_links(teaching):
    aldermoor = teaching["aldermoor"]
    with session_factory()() as db:
        set_db_context(db, tenant_id=aldermoor.id)
        db.add(LearningResource(institution_id=aldermoor.id, course_id=uuid.UUID(teaching["h101"]["course_id"]), subject_id=uuid.UUID(teaching["h101"]["id"]),
                                created_by_membership_id=teaching["faculty"].membership_id, title="x", resource_type="note", body="x"))
        with pytest.raises(IntegrityError, match="fk_learning_resources_subject_in_course"):
            db.flush()
        db.rollback()
        # Subject from one course, course from another (same institution): also rejected.
        other_course = teaching["admin"].post("/api/academic/courses", {"name": "BA", "code": "BA", "degree_level": "bachelor", "duration_semesters": 6}).json()
        db.add(LearningResource(institution_id=aldermoor.id, course_id=uuid.UUID(other_course["id"]), subject_id=uuid.UUID(teaching["cs101"]["id"]),
                                created_by_membership_id=teaching["faculty"].membership_id, title="x", resource_type="note", body="x"))
        with pytest.raises(IntegrityError, match="fk_learning_resources_subject_in_course"):
            db.flush()


def test_rls_isolation_and_no_delete(teaching):
    make(teaching["faculty"], teaching["cs101"]["id"])
    make(teaching["other_admin"], teaching["h101"]["id"])
    with session_factory()() as db:
        for tenant, expected in ((teaching["aldermoor"].id, 1), (teaching["halvard"].id, 1), (None, 0)):
            set_db_context(db, tenant_id=tenant)
            assert db.scalar(select(func.count()).select_from(LearningResource)) == expected
        set_db_context(db, tenant_id=teaching["aldermoor"].id)
        with pytest.raises(ProgrammingError, match="permission denied"):
            db.execute(text("DELETE FROM learning_resources"))
        db.rollback()
        set_db_context(db, tenant_id=teaching["aldermoor"].id)
        db.add(LearningResource(institution_id=teaching["halvard"].id, course_id=uuid.UUID(teaching["h101"]["course_id"]), subject_id=uuid.UUID(teaching["h101"]["id"]),
                                created_by_membership_id=teaching["faculty"].membership_id, title="x", resource_type="note", body="x"))
        with pytest.raises(ProgrammingError, match="row-level security"):
            db.flush()
