"""M4.5: assignments, submissions and grading."""

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError, ProgrammingError

from app.db.session import session_factory, set_db_context
from app.models import Assignment, Submission, SubmissionGrade


def iso(delta: timedelta) -> str:
    return (datetime.now(timezone.utc) + delta).isoformat()


def body(**overrides) -> dict:
    return {
        "title": "Problem set 1",
        "instructions": "Solve all five problems.",
        "available_from": iso(timedelta(days=-1)),
        "due_at": iso(timedelta(days=7)),
        "max_marks": 20,
        **overrides,
    }


def make(actor, subject_id, publish=True, **overrides) -> dict:
    r = actor.post(f"/api/academic/subjects/{subject_id}/assignments", body(**overrides))
    assert r.status_code == 201, r.text
    if publish:
        r = actor.post(f"/api/academic/assignments/{r.json()['id']}/publish")
        assert r.status_code == 200, r.text
    return r.json()


def submit(actor, assignment_id, text_="My answer"):
    return actor.post(f"/api/academic/assignments/{assignment_id}/submissions", {"body": text_})


# ---- Assignments --------------------------------------------------------------


def test_create_and_publish(teaching):
    faculty = teaching["faculty"]
    draft = make(faculty, teaching["cs101"]["id"], publish=False, reference_url="https://example.org/brief", late_policy="accept")
    assert draft["status"] == "draft" and draft["published_at"] is None and draft["window"] == "open"
    assert draft["max_marks"] == 20 and draft["late_policy"] == "accept" and draft["submitted_students"] == 0
    assert draft["due_at"].endswith("Z")
    published = faculty.post(f"/api/academic/assignments/{draft['id']}/publish").json()
    assert published["status"] == "published" and published["published_at"]
    edited = faculty.patch(f"/api/academic/assignments/{draft['id']}", {"title": "Problem set 1 (revised)", "max_marks": 25}).json()
    assert edited["title"] == "Problem set 1 (revised)" and edited["max_marks"] == 25
    archived = faculty.post(f"/api/academic/assignments/{draft['id']}/archive").json()
    assert archived["status"] == "archived"
    assert faculty.patch(f"/api/academic/assignments/{draft['id']}", {"title": "x"}).json()["code"] == "assignment_archived"
    assert faculty.post(f"/api/academic/assignments/{draft['id']}/publish").json()["code"] == "assignment_archived"


@pytest.mark.parametrize(
    "overrides",
    [
        {"due_at": iso(timedelta(days=-2))},  # before available_from
        {"available_from": "2027-03-01T09:00:00Z", "due_at": "2027-03-01T09:00:00Z"},  # equal
        {"late_policy": "accept_until"},  # no cut-off
        {"late_policy": "accept_until", "late_cutoff_at": iso(timedelta(days=6))},  # cut-off before due
        {"late_policy": "reject", "late_cutoff_at": iso(timedelta(days=9))},
        {"max_marks": 0},
        {"max_marks": 1001},
        {"max_marks": 10.555},
        {"due_at": "2027-01-01T09:00:00"},  # naive
        {"reference_url": "javascript:alert(1)"},
        {"late_policy": "whenever"},
        {"title": "  "},
        {"institution_id": str(uuid.uuid4())},
    ],
)
def test_assignment_validation(teaching, overrides):
    r = teaching["faculty"].post(f"/api/academic/subjects/{teaching['cs101']['id']}/assignments", body(**overrides))
    assert r.status_code == 422, r.text


def test_update_validates_merged_dates(teaching):
    a = make(teaching["faculty"], teaching["cs101"]["id"])
    r = teaching["faculty"].patch(f"/api/academic/assignments/{a['id']}", {"due_at": iso(timedelta(days=-3))})
    assert r.status_code == 422 and r.json()["code"] == "invalid_dates"


# ---- Visibility ---------------------------------------------------------------


def test_student_visibility_through_enrolment(teaching):
    faculty, student = teaching["faculty"], teaching["student"]
    live = make(faculty, teaching["cs101"]["id"])
    draft = make(faculty, teaching["cs101"]["id"], publish=False, title="Draft")
    future = make(faculty, teaching["cs101"]["id"], title="Later", available_from=iso(timedelta(days=2)), due_at=iso(timedelta(days=9)))
    mine = student.get("/api/academic/assignments/me").json()
    assert [a["id"] for a in mine] == [live["id"]]
    assert mine[0]["me"] == {"status": "not_submitted", "attempts": 0, "last_submitted_at": None, "is_late": False, "grade": None}
    assert mine[0]["submitted_students"] is None  # managers-only counters
    for hidden in (draft, future):
        assert student.get(f"/api/academic/assignments/{hidden['id']}").status_code == 404
    assert [a["id"] for a in student.get(f"/api/academic/subjects/{teaching['cs101']['id']}/assignments").json()] == [live["id"]]
    # Unenrolled student: nothing.
    assert teaching["student2"].get("/api/academic/assignments/me").json() == []
    assert teaching["student2"].get(f"/api/academic/assignments/{live['id']}").status_code == 404


def test_archived_assignment_stays_visible_only_to_submitters(teaching):
    faculty, student = teaching["faculty"], teaching["student"]
    a = make(faculty, teaching["cs101"]["id"])
    b = make(faculty, teaching["cs101"]["id"], title="Unsubmitted")
    assert submit(student, a["id"]).status_code == 201
    faculty.post(f"/api/academic/assignments/{a['id']}/archive")
    faculty.post(f"/api/academic/assignments/{b['id']}/archive")
    assert [x["id"] for x in student.get("/api/academic/assignments/me").json()] == [a["id"]]
    assert submit(student, a["id"]).json()["code"] == "assignment_closed"
    assert len(student.get(f"/api/academic/assignments/{a['id']}/submissions/me").json()) == 1


# ---- Submissions --------------------------------------------------------------


def test_submission_and_history(teaching):
    student = teaching["student"]
    a = make(teaching["faculty"], teaching["cs101"]["id"])
    first = submit(student, a["id"], "First try")
    assert first.status_code == 201
    first = first.json()
    assert first["attempt"] == 1 and first["is_late"] is False and first["status"] == "submitted" and first["grade"] is None
    second = submit(student, a["id"], "Second try").json()
    assert second["attempt"] == 2
    history = student.get(f"/api/academic/assignments/{a['id']}/submissions/me").json()
    assert [(s["attempt"], s["body"], s["status"]) for s in history] == [(1, "First try", "superseded"), (2, "Second try", "submitted")]
    progress = student.get(f"/api/academic/assignments/{a['id']}").json()["me"]
    assert progress["status"] == "submitted" and progress["attempts"] == 2


def test_blank_or_unauthorised_submissions(teaching):
    a = make(teaching["faculty"], teaching["cs101"]["id"])
    assert submit(teaching["student"], a["id"], "   ").status_code == 422
    assert teaching["student"].post(f"/api/academic/assignments/{a['id']}/submissions", {"body": "x", "is_late": False}).status_code == 422
    assert submit(teaching["student2"], a["id"]).status_code == 404  # not enrolled
    assert submit(teaching["faculty"], a["id"]).json()["code"] == "insufficient_role"
    draft = make(teaching["faculty"], teaching["cs101"]["id"], publish=False)
    assert submit(teaching["student"], draft["id"]).status_code == 404


def test_withdrawn_student_cannot_submit(teaching):
    admin, student = teaching["admin"], teaching["student"]
    a = make(teaching["faculty"], teaching["cs101"]["id"])
    enrolment = student.get("/api/academic/enrolments/me").json()[0]
    admin.patch(f"/api/academic/enrolments/{enrolment['id']}", {"status": "withdrawn"})
    assert submit(student, a["id"]).status_code == 404


# ---- Deadlines ----------------------------------------------------------------

PAST = dict(available_from=iso(timedelta(days=-10)), due_at=iso(timedelta(days=-1)))


def test_reject_policy_closes_at_deadline(teaching):
    a = make(teaching["faculty"], teaching["cs101"]["id"], **PAST)
    assert a["window"] == "closed"
    r = submit(teaching["student"], a["id"])
    assert r.status_code == 409 and r.json()["code"] == "deadline_passed"


def test_accept_policy_flags_late(teaching):
    a = make(teaching["faculty"], teaching["cs101"]["id"], late_policy="accept", **PAST)
    assert a["window"] == "late"
    s = submit(teaching["student"], a["id"]).json()
    assert s["is_late"] is True
    assert teaching["student"].get(f"/api/academic/assignments/{a['id']}").json()["me"]["is_late"] is True


def test_accept_until_policy(teaching):
    open_late = make(teaching["faculty"], teaching["cs101"]["id"], late_policy="accept_until", late_cutoff_at=iso(timedelta(days=1)), **PAST)
    assert submit(teaching["student"], open_late["id"]).json()["is_late"] is True
    closed = make(
        teaching["faculty"], teaching["cs101"]["id"], late_policy="accept_until",
        available_from=iso(timedelta(days=-10)), due_at=iso(timedelta(days=-3)), late_cutoff_at=iso(timedelta(days=-1)),
    )
    assert submit(teaching["student"], closed["id"]).json()["code"] == "deadline_passed"


def test_on_time_submission_not_late(teaching):
    a = make(teaching["faculty"], teaching["cs101"]["id"], late_policy="accept")
    assert submit(teaching["student"], a["id"]).json()["is_late"] is False


def test_lateness_is_fixed_at_submission_time(teaching):
    faculty = teaching["faculty"]
    a = make(faculty, teaching["cs101"]["id"], late_policy="accept", **PAST)
    s = submit(teaching["student"], a["id"]).json()
    faculty.patch(f"/api/academic/assignments/{a['id']}", {"due_at": iso(timedelta(days=5))})
    assert teaching["student"].get(f"/api/academic/submissions/{s['id']}").json()["is_late"] is True


# ---- Grading ------------------------------------------------------------------


def test_grading_and_regrading_history(teaching):
    faculty, student = teaching["faculty"], teaching["student"]
    a = make(faculty, teaching["cs101"]["id"])
    s = submit(student, a["id"]).json()
    g1 = faculty.post(f"/api/academic/submissions/{s['id']}/grades", {"marks_awarded": 14.5, "feedback": "Good start"})
    assert g1.status_code == 201, g1.text
    assert g1.json()["status"] == "graded" and g1.json()["grade"]["marks_awarded"] == 14.5
    g2 = faculty.post(f"/api/academic/submissions/{s['id']}/grades", {"marks_awarded": 16, "feedback": "Regraded after review"}).json()
    assert [g["marks_awarded"] for g in g2["grade_history"]] == [14.5, 16] and g2["grade"]["feedback"] == "Regraded after review"
    assert g2["grade"]["graded_by"]["full_name"] == "Ada Prof"
    mine = student.get(f"/api/academic/assignments/{a['id']}").json()["me"]
    assert mine["status"] == "graded" and mine["grade"]["marks_awarded"] == 16
    listed = faculty.get(f"/api/academic/assignments/managed?subject_id={teaching['cs101']['id']}").json()[0]
    assert listed["submitted_students"] == 1 and listed["graded_students"] == 1


@pytest.mark.parametrize("marks,code", [(20.5, 422), (-1, 422), (10.123, 422)])
def test_grade_validation(teaching, marks, code):
    a = make(teaching["faculty"], teaching["cs101"]["id"])
    s = submit(teaching["student"], a["id"]).json()
    r = teaching["faculty"].post(f"/api/academic/submissions/{s['id']}/grades", {"marks_awarded": marks})
    assert r.status_code == code


def test_max_marks_cannot_drop_below_awarded(teaching):
    faculty = teaching["faculty"]
    a = make(faculty, teaching["cs101"]["id"])
    s = submit(teaching["student"], a["id"]).json()
    faculty.post(f"/api/academic/submissions/{s['id']}/grades", {"marks_awarded": 18})
    r = faculty.patch(f"/api/academic/assignments/{a['id']}", {"max_marks": 15})
    assert r.status_code == 409 and r.json()["code"] == "max_marks_below_grades"


def test_faculty_grading_permissions(teaching):
    a = make(teaching["faculty"], teaching["cs101"]["id"])
    s = submit(teaching["student"], a["id"]).json()
    other = teaching["faculty2"]  # teaches CS102 only
    r = other.post(f"/api/academic/submissions/{s['id']}/grades", {"marks_awarded": 10})
    assert r.status_code == 403 and r.json()["code"] == "not_assigned"
    assert other.get(f"/api/academic/assignments/{a['id']}/submissions").status_code == 403
    assert other.get(f"/api/academic/submissions/{s['id']}").status_code == 404
    assert other.post(f"/api/academic/subjects/{teaching['cs101']['id']}/assignments", body()).status_code == 403
    assert other.patch(f"/api/academic/assignments/{a['id']}", {"title": "x"}).status_code == 403
    # Admins grade anything in their institution.
    assert teaching["admin"].post(f"/api/academic/submissions/{s['id']}/grades", {"marks_awarded": 12}).status_code == 201


def test_students_cannot_grade_or_manage(teaching):
    student = teaching["student"]
    a = make(teaching["faculty"], teaching["cs101"]["id"])
    s = submit(student, a["id"]).json()
    assert student.post(f"/api/academic/submissions/{s['id']}/grades", {"marks_awarded": 20}).status_code == 403
    assert student.post(f"/api/academic/subjects/{teaching['cs101']['id']}/assignments", body()).status_code == 403
    assert student.patch(f"/api/academic/assignments/{a['id']}", {"max_marks": 100}).status_code == 403
    assert student.get(f"/api/academic/assignments/{a['id']}/submissions").status_code == 403
    assert student.get("/api/academic/assignments/managed").status_code == 403


def test_student_cannot_see_another_students_submission(teaching, make_client):
    from app.models import MembershipRole
    from tests.helpers import enrol, membership_of, sign_in

    a = make(teaching["faculty"], teaching["cs101"]["id"])
    classmate = sign_in(make_client, "zoe@aldermoor.example", [(teaching["aldermoor"], MembershipRole.student)], name="Zoe")
    enrol(teaching["admin"], membership_of(classmate.user, teaching["aldermoor"]).id, teaching["course"]["id"])
    theirs = submit(classmate, a["id"], "Zoe's work").json()
    student = teaching["student"]
    assert student.get(f"/api/academic/submissions/{theirs['id']}").status_code == 404
    assert student.get(f"/api/academic/assignments/{a['id']}/submissions/me").json() == []
    # Faculty roster shows both, latest-only filter works.
    submit(student, a["id"]); submit(student, a["id"])
    all_subs = teaching["faculty"].get(f"/api/academic/assignments/{a['id']}/submissions").json()
    latest = teaching["faculty"].get(f"/api/academic/assignments/{a['id']}/submissions?latest_only=true").json()
    assert len(all_subs) == 3 and sorted(s["attempt"] for s in latest) == [1, 2]


# ---- Tenant isolation and history integrity -------------------------------------


def test_cross_institution_access_denied(teaching):
    a = make(teaching["faculty"], teaching["cs101"]["id"])
    s = submit(teaching["student"], a["id"]).json()
    other = teaching["other_admin"]
    checks = [
        other.get(f"/api/academic/assignments/{a['id']}"),
        other.patch(f"/api/academic/assignments/{a['id']}", {"title": "x"}),
        other.post(f"/api/academic/assignments/{a['id']}/archive"),
        other.get(f"/api/academic/assignments/{a['id']}/submissions"),
        other.get(f"/api/academic/submissions/{s['id']}"),
        other.post(f"/api/academic/submissions/{s['id']}/grades", {"marks_awarded": 1}),
        other.post(f"/api/academic/subjects/{teaching['cs101']['id']}/assignments", body()),
        submit(teaching["other_student"], a["id"]),
    ]
    assert [r.status_code for r in checks] == [404] * len(checks)
    assert other.get("/api/academic/assignments/managed").json() == []


def test_history_is_append_only_in_the_database(teaching):
    a = make(teaching["faculty"], teaching["cs101"]["id"])
    s = submit(teaching["student"], a["id"]).json()
    teaching["faculty"].post(f"/api/academic/submissions/{s['id']}/grades", {"marks_awarded": 10})
    with session_factory()() as db:
        set_db_context(db, tenant_id=teaching["aldermoor"].id)
        for sql in (
            "UPDATE submissions SET body = 'rewritten'",
            "UPDATE submission_grades SET marks_awarded = 20",
            "DELETE FROM submission_grades",
            "DELETE FROM submissions",
            "DELETE FROM assignments",
        ):
            with pytest.raises(ProgrammingError, match="permission denied"):
                db.execute(text(sql))
            db.rollback()
            set_db_context(db, tenant_id=teaching["aldermoor"].id)


def test_database_rejects_cross_institution_links(teaching):
    a = make(teaching["faculty"], teaching["cs101"]["id"])
    aldermoor = teaching["aldermoor"]
    with session_factory()() as db:
        set_db_context(db, tenant_id=aldermoor.id)
        db.add(Submission(institution_id=aldermoor.id, assignment_id=uuid.UUID(a["id"]), student_membership_id=teaching["other_student"].membership_id,
                          attempt=1, body="x", is_late=False))
        with pytest.raises(IntegrityError, match="fk_submissions_student_same_institution"):
            db.flush()


def test_rls_isolation(teaching):
    a = make(teaching["faculty"], teaching["cs101"]["id"])
    s = submit(teaching["student"], a["id"]).json()
    teaching["faculty"].post(f"/api/academic/submissions/{s['id']}/grades", {"marks_awarded": 10})
    with session_factory()() as db:
        for tenant, expected in ((teaching["aldermoor"].id, 1), (teaching["halvard"].id, 0), (None, 0)):
            set_db_context(db, tenant_id=tenant)
            for model in (Assignment, Submission, SubmissionGrade):
                assert db.scalar(select(func.count()).select_from(model)) == expected, (model, tenant)
        set_db_context(db, tenant_id=teaching["halvard"].id)
        db.add(Submission(institution_id=aldermoor_id(teaching), assignment_id=uuid.UUID(a["id"]),
                          student_membership_id=teaching["student"].membership_id, attempt=9, body="x", is_late=False))
        with pytest.raises(ProgrammingError, match="row-level security"):
            db.flush()


def aldermoor_id(teaching):
    return teaching["aldermoor"].id
