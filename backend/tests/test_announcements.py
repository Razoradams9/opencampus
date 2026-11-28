"""M4.6: academic announcements."""

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError, ProgrammingError

from app.db.session import session_factory, set_db_context
from app.models import Announcement
from tests.helpers import create_course


def post(actor, publish=True, **fields):
    body = {"title": "Notice", "body": "Details here.", **fields}
    r = actor.post("/api/academic/announcements", body)
    assert r.status_code == 201, r.text
    if publish:
        r = actor.post(f"/api/academic/announcements/{r.json()['id']}/publish")
        assert r.status_code == 200, r.text
    return r.json()


def feed_ids(actor, **params):
    query = "&".join(f"{k}={v}" for k, v in params.items())
    r = actor.get(f"/api/academic/announcements?{query}")
    assert r.status_code == 200, r.text
    return {a["id"] for a in r.json()}


@pytest.fixture
def notices(teaching):
    """One published announcement per audience, by the right authors."""
    admin = teaching["admin"]
    other_course = create_course(admin, code="BA-ENG")
    return {
        "inst": post(admin, audience="institution", title="Campus closed Friday", priority="urgent"),
        "course": post(admin, audience="course", course_id=teaching["course"]["id"], title="BSC-CS orientation"),
        "other_course": post(admin, audience="course", course_id=other_course["id"], title="BA-ENG only"),
        "cs101": post(teaching["faculty"], audience="subject", subject_id=teaching["cs101"]["id"], title="CS101 room change", priority="important"),
        "cs101_students": post(teaching["faculty"], audience="subject_students", subject_id=teaching["cs101"]["id"], title="CS101 quiz"),
        "cs102": post(teaching["faculty2"], audience="subject", subject_id=teaching["cs102"]["id"], title="CS102 notes"),
    }


# ---- Creation and publication ----------------------------------------------------


def test_create_and_publish(teaching):
    draft = post(teaching["faculty"], publish=False, audience="subject", subject_id=teaching["cs101"]["id"], priority="important")
    assert draft["status"] == "draft" and draft["published_at"] is None
    assert draft["subject"]["code"] == "CS101" and draft["course"]["code"] == "BSC-CS"  # course derived
    assert draft["created_by"]["full_name"] == "Ada Prof"
    edited = teaching["faculty"].patch(f"/api/academic/announcements/{draft['id']}", {"title": "Updated", "priority": "urgent"}).json()
    assert edited["title"] == "Updated" and edited["priority"] == "urgent"
    published = teaching["faculty"].post(f"/api/academic/announcements/{draft['id']}/publish").json()
    assert published["status"] == "published" and published["published_at"].endswith("Z")
    r = teaching["faculty"].patch(f"/api/academic/announcements/{draft['id']}", {"title": "Too late"})
    assert r.status_code == 409 and r.json()["code"] == "announcement_not_draft"
    archived = teaching["faculty"].post(f"/api/academic/announcements/{draft['id']}/archive").json()
    assert archived["status"] == "archived"
    assert teaching["faculty"].post(f"/api/academic/announcements/{draft['id']}/publish").json()["code"] == "announcement_archived"


@pytest.mark.parametrize(
    "fields",
    [
        {"audience": "institution", "course_id": str(uuid.uuid4())},
        {"audience": "course"},
        {"audience": "subject"},
        {"audience": "subject", "subject_id": str(uuid.uuid4()), "course_id": str(uuid.uuid4())},
        {"audience": "everyone"},
        {"audience": "institution", "priority": "critical"},
        {"audience": "institution", "body": "   "},
        {"audience": "institution", "expires_at": "2027-01-01T00:00:00"},  # naive
        {"audience": "institution", "institution_id": str(uuid.uuid4())},
        {"audience": "institution", "status": "published"},
    ],
)
def test_validation(teaching, fields):
    assert teaching["admin"].post("/api/academic/announcements", {"title": "x", "body": "y", **fields}).status_code == 422


# ---- Visibility -----------------------------------------------------------------


def test_student_feed_is_targeted(teaching, notices):
    ids = feed_ids(teaching["student"])
    expected = {notices[k]["id"] for k in ("inst", "course", "cs101", "cs101_students", "cs102")}
    assert ids == expected  # not the other course's
    # A student without an enrolment sees only institution-wide notices.
    assert feed_ids(teaching["student2"]) == {notices["inst"]["id"]}
    assert teaching["student2"].get(f"/api/academic/announcements/{notices['cs101']['id']}").status_code == 404


def test_faculty_feed_is_targeted(teaching, notices):
    # Faculty: institution, courses they teach in, subjects they teach; never
    # student-only notices, other subjects or other courses.
    assert feed_ids(teaching["faculty"]) == {notices["inst"]["id"], notices["course"]["id"], notices["cs101"]["id"]}
    assert feed_ids(teaching["faculty2"]) == {notices["inst"]["id"], notices["course"]["id"], notices["cs102"]["id"]}
    # The author of a student-only notice reaches it through management, not the feed.
    assert teaching["faculty"].get(f"/api/academic/announcements/{notices['cs101_students']['id']}").status_code == 200
    assert teaching["faculty2"].get(f"/api/academic/announcements/{notices['cs101_students']['id']}").status_code == 404


def test_admin_sees_everything_published(teaching, notices):
    assert feed_ids(teaching["admin"]) == {n["id"] for n in notices.values()}


def test_withdrawal_removes_course_notices(teaching, notices):
    student = teaching["student"]
    enrolment = student.get("/api/academic/enrolments/me").json()[0]
    teaching["admin"].patch(f"/api/academic/enrolments/{enrolment['id']}", {"status": "withdrawn"})
    assert feed_ids(student) == {notices["inst"]["id"]}


def test_drafts_and_archived_never_in_feeds(teaching):
    draft = post(teaching["admin"], publish=False, audience="institution", title="Draft")
    archived = post(teaching["admin"], audience="institution", title="Old")
    teaching["admin"].post(f"/api/academic/announcements/{archived['id']}/archive")
    for actor in (teaching["student"], teaching["faculty"], teaching["admin"]):
        ids = feed_ids(actor) | feed_ids(actor, include_expired="true")
        assert draft["id"] not in ids and archived["id"] not in ids
    assert teaching["student"].get(f"/api/academic/announcements/{draft['id']}").status_code == 404
    assert teaching["student"].get(f"/api/academic/announcements/{archived['id']}").status_code == 404
    # Managers still see both.
    managed = {a["id"] for a in teaching["admin"].get("/api/academic/announcements/managed").json()}
    assert {draft["id"], archived["id"]} <= managed


def test_expiry(teaching):
    soon = (datetime.now(timezone.utc) + timedelta(days=2)).isoformat()
    live = post(teaching["admin"], audience="institution", title="Live", expires_at=soon)
    gone = post(teaching["admin"], audience="institution", title="Expired")
    with session_factory()() as db:  # move it into the past (published 2 h ago, expired 1 h ago)
        set_db_context(db, tenant_id=teaching["aldermoor"].id)
        db.execute(text("UPDATE announcements SET published_at = now() - interval '2 hours', expires_at = now() - interval '1 hour' WHERE id = :id"), {"id": gone["id"]})
        db.commit()
    student = teaching["student"]
    assert feed_ids(student) == {live["id"]}
    with_expired = {a["id"]: a for a in student.get("/api/academic/announcements?include_expired=true").json()}
    assert with_expired[gone["id"]]["expired"] is True and with_expired[live["id"]]["expired"] is False
    assert student.get(f"/api/academic/announcements/{gone['id']}").json()["expired"] is True


def test_cannot_publish_already_expired(teaching):
    draft = post(teaching["admin"], publish=False, audience="institution")
    with session_factory()() as db:
        set_db_context(db, tenant_id=teaching["aldermoor"].id)
        db.execute(text("UPDATE announcements SET expires_at = now() - interval '1 minute' WHERE id = :id"), {"id": draft["id"]})
        db.commit()
    r = teaching["admin"].post(f"/api/academic/announcements/{draft['id']}/publish")
    assert r.status_code == 422 and r.json()["code"] == "already_expired"


# ---- Authoring restrictions ---------------------------------------------------------


def test_faculty_audience_restrictions(teaching):
    faculty = teaching["faculty"]
    for fields in (
        {"audience": "institution"},
        {"audience": "course", "course_id": teaching["course"]["id"]},
        {"audience": "subject", "subject_id": teaching["cs102"]["id"]},  # not their subject
        {"audience": "subject_students", "subject_id": teaching["cs102"]["id"]},
    ):
        r = faculty.post("/api/academic/announcements", {"title": "x", "body": "y", **fields})
        assert r.status_code == 403 and r.json()["code"] == "audience_not_permitted", fields


def test_audience_cannot_be_widened_by_editing(teaching):
    faculty = teaching["faculty"]
    draft = post(faculty, publish=False, audience="subject", subject_id=teaching["cs101"]["id"])
    for change in (
        {"audience": "institution"},
        {"audience": "course", "course_id": teaching["course"]["id"]},
        {"subject_id": teaching["cs102"]["id"]},
    ):
        r = faculty.patch(f"/api/academic/announcements/{draft['id']}", change)
        assert r.status_code in (403, 422), (change, r.text)
    # Inconsistent target fields are rejected before any permission check.
    assert faculty.patch(f"/api/academic/announcements/{draft['id']}", {"audience": "subject"}).json()["code"] == "invalid_audience"
    # Re-targeting to another subject they teach is fine.
    assert faculty.patch(f"/api/academic/announcements/{draft['id']}", {"audience": "subject_students", "subject_id": teaching["cs101"]["id"]}).status_code == 200


def test_faculty_who_lost_assignment_cannot_publish(teaching):
    faculty = teaching["faculty"]
    draft = post(faculty, publish=False, audience="subject", subject_id=teaching["cs101"]["id"])
    assignment = faculty.get("/api/academic/faculty-assignments/me").json()[0]
    teaching["admin"].post(f"/api/academic/faculty-assignments/{assignment['id']}/end")
    assert faculty.post(f"/api/academic/announcements/{draft['id']}/publish").status_code == 404
    assert faculty.get("/api/academic/announcements/managed").json() == []


def test_faculty_cannot_manage_others_announcements(teaching, notices):
    faculty = teaching["faculty"]
    for target in ("inst", "course", "cs102"):
        aid = notices[target]["id"]
        assert faculty.post(f"/api/academic/announcements/{aid}/archive").status_code == 404
    managed = {a["id"] for a in faculty.get("/api/academic/announcements/managed").json()}
    assert managed == {notices["cs101"]["id"], notices["cs101_students"]["id"]}


def test_students_cannot_author(teaching):
    student = teaching["student"]
    r = student.post("/api/academic/announcements", {"title": "x", "body": "y", "audience": "subject", "subject_id": teaching["cs101"]["id"]})
    assert r.status_code == 403
    assert student.get("/api/academic/announcements/managed").status_code == 403
    a = post(teaching["admin"], audience="institution")
    assert student.post(f"/api/academic/announcements/{a['id']}/archive").status_code == 403


# ---- Tenant isolation -----------------------------------------------------------------


def test_cross_institution_access_denied(teaching, notices):
    other = teaching["other_admin"]
    theirs = post(other, audience="institution", title="Halvard news")
    assert feed_ids(teaching["student"]).isdisjoint({theirs["id"]})
    assert feed_ids(teaching["other_student"]) == {theirs["id"]}
    checks = [
        other.get(f"/api/academic/announcements/{notices['inst']['id']}"),
        other.post(f"/api/academic/announcements/{notices['inst']['id']}/archive"),
        other.patch(f"/api/academic/announcements/{notices['inst']['id']}", {"title": "x"}),
        other.post("/api/academic/announcements", {"title": "x", "body": "y", "audience": "course", "course_id": teaching["course"]["id"]}),
        other.post("/api/academic/announcements", {"title": "x", "body": "y", "audience": "subject", "subject_id": teaching["cs101"]["id"]}),
        teaching["admin"].get(f"/api/academic/announcements/{theirs['id']}"),
    ]
    assert [r.status_code for r in checks] == [404] * len(checks)


def test_database_constraints(teaching):
    aldermoor = teaching["aldermoor"]
    author = teaching["admin"].membership_id
    with session_factory()() as db:
        set_db_context(db, tenant_id=aldermoor.id)
        # Target another institution's subject.
        h = teaching["h101"]
        db.add(Announcement(institution_id=aldermoor.id, created_by_membership_id=author, title="x", body="y", audience="subject",
                            course_id=uuid.UUID(h["course_id"]), subject_id=uuid.UUID(h["id"])))
        with pytest.raises(IntegrityError, match="fk_announcements_"):
            db.flush()
        db.rollback()
        set_db_context(db, tenant_id=aldermoor.id)
        # Audience/target mismatch.
        db.add(Announcement(institution_id=aldermoor.id, created_by_membership_id=author, title="x", body="y", audience="institution",
                            course_id=uuid.UUID(teaching["course"]["id"])))
        with pytest.raises(IntegrityError, match="ck_announcements_audience_target"):
            db.flush()


def test_rls_isolation_and_no_delete(teaching):
    post(teaching["admin"], audience="institution")
    post(teaching["other_admin"], audience="institution")
    with session_factory()() as db:
        for tenant, expected in ((teaching["aldermoor"].id, 1), (teaching["halvard"].id, 1), (None, 0)):
            set_db_context(db, tenant_id=tenant)
            assert db.scalar(select(func.count()).select_from(Announcement)) == expected
        set_db_context(db, tenant_id=teaching["aldermoor"].id)
        with pytest.raises(ProgrammingError, match="permission denied"):
            db.execute(text("DELETE FROM announcements"))
        db.rollback()
        set_db_context(db, tenant_id=teaching["aldermoor"].id)
        db.add(Announcement(institution_id=teaching["halvard"].id, created_by_membership_id=teaching["other_admin"].membership_id,
                            title="x", body="y", audience="institution"))
        with pytest.raises(ProgrammingError, match="row-level security"):
            db.flush()
