"""M4.3: rooms, faculty assignments, class sessions and timetables."""

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import func, select, text, update
from sqlalchemy.exc import IntegrityError, ProgrammingError

from app.db.session import session_factory, set_db_context
from app.models import ClassSession, FacultyAssignment, Institution, MembershipRole, Room
from tests.helpers import create_course, create_subject, enrol, make_user, membership_of, sign_in

UTC = timezone.utc
MONDAY = datetime(2027, 1, 4, tzinfo=UTC)  # a Monday in the future


def at(day: int, hour: int, minute: int = 0) -> str:
    return (MONDAY + timedelta(days=day, hours=hour, minutes=minute)).isoformat()


@pytest.fixture
def setup(college):
    """Aldermoor: course with two subjects, a room, the faculty member assigned
    to CS101 for 2026-27 / Semester 1, and Maya enrolled for that period."""
    admin = college["admin"]
    course = create_course(admin, code="BSC-CS")
    cs101 = create_subject(admin, course["id"], code="CS101")
    cs102 = create_subject(admin, course["id"], code="CS102", name="Discrete Maths")
    room = admin.post("/api/academic/rooms", {"name": "Lab 1", "building": "Turing", "capacity": 40}).json()
    assignment = assign(admin, cs101["id"], college["faculty"].membership_id)
    enrol(admin, college["student"].membership_id, course["id"])
    return {"course": course, "cs101": cs101, "cs102": cs102, "room": room, "assignment": assignment}


def assign(actor, subject_id, membership_id, *, year="2026-27", period="Semester 1") -> dict:
    response = actor.post(
        "/api/academic/faculty-assignments",
        {"subject_id": subject_id, "faculty_membership_id": str(membership_id), "academic_year": year, "academic_period": period},
    )
    assert response.status_code == 201, response.text
    return response.json()


def schedule(actor, assignment_id, start, end, room_id=None):
    body = {"faculty_assignment_id": assignment_id, "start_at": start, "end_at": end}
    if room_id is not None:
        body["room_id"] = room_id
    return actor.post("/api/academic/timetable/sessions", body)


def second_faculty(college, make_client):
    actor = sign_in(make_client, "lin@aldermoor.example", [(college["aldermoor"], MembershipRole.faculty)], name="Lin Chen")
    actor.membership_id = membership_of(actor.user, college["aldermoor"]).id
    return actor


# ---- Rooms -----------------------------------------------------------------


def test_room_management(college):
    admin = college["admin"]
    room = admin.post("/api/academic/rooms", {"name": " Lab  1 ", "building": "Turing", "capacity": 30}).json()
    assert room["name"] == "Lab 1" and room["status"] == "active"
    dup = admin.post("/api/academic/rooms", {"name": "Lab 1", "building": "Turing"})
    assert dup.status_code == 409 and dup.json()["code"] == "room_exists"
    admin.post("/api/academic/rooms", {"name": "Lab 1", "building": "Hopper"})  # other building: fine
    assert admin.patch(f"/api/academic/rooms/{room['id']}", {"capacity": None}).json()["capacity"] is None
    assert admin.post("/api/academic/rooms", {"name": "X", "capacity": 0}).status_code == 422

    assert admin.post(f"/api/academic/rooms/{room['id']}/archive").json()["status"] == "archived"
    assert [r["building"] for r in college["student"].get("/api/academic/rooms").json()] == ["Hopper"]
    assert college["student"].post("/api/academic/rooms", {"name": "Mine"}).status_code == 403
    assert college["faculty"].patch(f"/api/academic/rooms/{room['id']}", {"name": "Mine"}).status_code == 403


def test_room_with_upcoming_sessions_cannot_be_archived(college, setup):
    admin = college["admin"]
    assert schedule(admin, setup["assignment"]["id"], at(0, 9), at(0, 10), setup["room"]["id"]).status_code == 201
    response = admin.post(f"/api/academic/rooms/{setup['room']['id']}/archive")
    assert response.status_code == 409 and response.json()["code"] == "room_has_sessions"


# ---- Faculty assignments ---------------------------------------------------


def test_assignment_derives_course_from_subject(college, setup):
    a = setup["assignment"]
    assert a["course"]["id"] == setup["course"]["id"] and a["subject"]["code"] == "CS101"
    assert a["faculty"]["full_name"] == "Ada Prof" and a["status"] == "active"
    # course_id is not an accepted input: it cannot disagree with the subject.
    body = {"subject_id": setup["cs102"]["id"], "faculty_membership_id": str(college["faculty"].membership_id),
            "academic_year": "2026-27", "academic_period": "S1", "course_id": str(uuid.uuid4())}
    assert college["admin"].post("/api/academic/faculty-assignments", body).status_code == 422


def test_assignment_validation(college, setup):
    admin = college["admin"]
    body = {"subject_id": setup["cs101"]["id"], "academic_year": "2026-27", "academic_period": "Semester 1"}
    dup = admin.post("/api/academic/faculty-assignments", {**body, "faculty_membership_id": str(college["faculty"].membership_id)})
    assert dup.status_code == 409 and dup.json()["code"] == "assignment_exists"
    for key in ("student", "admin"):
        r = admin.post("/api/academic/faculty-assignments", {**body, "faculty_membership_id": str(college[key].membership_id)})
        assert r.status_code == 409 and r.json()["code"] == "not_an_active_faculty"
    admin.post(f"/api/academic/subjects/{setup['cs102']['id']}/archive")
    r = admin.post("/api/academic/faculty-assignments", {**body, "subject_id": setup["cs102"]["id"], "faculty_membership_id": str(college["faculty"].membership_id)})
    assert r.status_code == 409 and r.json()["code"] == "subject_archived"


def test_suspended_faculty_cannot_be_assigned_or_scheduled(college, setup):
    admin = college["admin"]
    admin.patch(f"/api/institution/members/{college['faculty'].membership_id}", {"status": "suspended"})
    r = schedule(admin, setup["assignment"]["id"], at(0, 9), at(0, 10))
    assert r.status_code == 409 and r.json()["code"] == "not_an_active_faculty"


def test_assignment_access(college, setup, make_client):
    other = second_faculty(college, make_client)
    assign(college["admin"], setup["cs102"]["id"], other.membership_id)
    faculty = college["faculty"]
    assert [a["subject"]["code"] for a in faculty.get("/api/academic/faculty-assignments/me").json()] == ["CS101"]
    assert [a["subject"]["code"] for a in faculty.get("/api/academic/faculty-assignments").json()] == ["CS101"]
    assert faculty.get(f"/api/academic/faculty-assignments/{setup['assignment']['id']}").status_code == 200
    theirs = other.get("/api/academic/faculty-assignments/me").json()[0]
    assert faculty.get(f"/api/academic/faculty-assignments/{theirs['id']}").status_code == 404
    assert len(college["admin"].get("/api/academic/faculty-assignments").json()) == 2
    assert college["student"].get("/api/academic/faculty-assignments").status_code == 403
    assert college["student"].get("/api/academic/faculty-assignments/me").json() == []
    assert faculty.post("/api/academic/faculty-assignments", {}).status_code in (403, 422)
    assert faculty.post(f"/api/academic/faculty-assignments/{theirs['id']}/end").status_code == 403


def test_ending_assignments(college, setup):
    admin, a = college["admin"], setup["assignment"]
    session = schedule(admin, a["id"], at(0, 9), at(0, 10)).json()
    blocked = admin.post(f"/api/academic/faculty-assignments/{a['id']}/end")
    assert blocked.status_code == 409 and blocked.json()["code"] == "assignment_has_sessions"
    admin.post(f"/api/academic/timetable/sessions/{session['id']}/cancel")
    assert admin.post(f"/api/academic/faculty-assignments/{a['id']}/end").json()["status"] == "ended"
    r = schedule(admin, a["id"], at(1, 9), at(1, 10))
    assert r.status_code == 409 and r.json()["code"] == "assignment_ended"
    assign(admin, setup["cs101"]["id"], college["faculty"].membership_id)  # a new active one is allowed again


# ---- Sessions --------------------------------------------------------------


def test_create_session(college, setup):
    r = schedule(college["admin"], setup["assignment"]["id"], "2027-01-04T14:30:00+05:30", "2027-01-04T15:30:00+05:30", setup["room"]["id"])
    assert r.status_code == 201, r.text
    s = r.json()
    assert s["start_at"] == "2027-01-04T09:00:00Z" and s["end_at"] == "2027-01-04T10:00:00Z"
    assert s["status"] == "scheduled"
    # Read back from the database: still UTC.
    assert college["admin"].get(f"/api/academic/timetable/sessions/{s['id']}").json()["start_at"] == "2027-01-04T09:00:00Z"
    assert s["course"]["code"] == "BSC-CS" and s["subject"]["code"] == "CS101"
    assert s["faculty"] == {"membership_id": str(college["faculty"].membership_id), "full_name": "Ada Prof"}
    assert s["room"]["name"] == "Lab 1" and s["academic_period"] == "Semester 1"
    assert "email" not in s["faculty"]


@pytest.mark.parametrize(
    "start,end,code",
    [
        (at(0, 10), at(0, 10), "invalid_time_range"),
        (at(0, 10), at(0, 9), "invalid_time_range"),
        (at(0, 6), at(0, 19), "invalid_time_range"),  # 13 hours
    ],
)
def test_invalid_intervals(college, setup, start, end, code):
    r = schedule(college["admin"], setup["assignment"]["id"], start, end)
    assert r.status_code == 422 and r.json()["code"] == code


def test_naive_timestamps_rejected(college, setup):
    assert schedule(college["admin"], setup["assignment"]["id"], "2027-01-04T09:00:00", "2027-01-04T10:00:00").status_code == 422


def test_room_conflicts(college, setup, make_client):
    admin, room = college["admin"], setup["room"]["id"]
    other = second_faculty(college, make_client)
    other_assignment = assign(admin, setup["cs102"]["id"], other.membership_id)
    assert schedule(admin, setup["assignment"]["id"], at(0, 9), at(0, 10), room).status_code == 201

    clash = schedule(admin, other_assignment["id"], at(0, 9, 30), at(0, 10, 30), room)
    assert clash.status_code == 409 and clash.json()["code"] == "room_conflict"
    contained = schedule(admin, other_assignment["id"], at(0, 9, 15), at(0, 9, 45), room)
    assert contained.json()["code"] == "room_conflict"
    # Half-open intervals: back-to-back bookings are fine; so is no room.
    assert schedule(admin, other_assignment["id"], at(0, 10), at(0, 11), room).status_code == 201
    assert schedule(admin, other_assignment["id"], at(0, 8), at(0, 9), room).status_code == 201


def test_faculty_conflicts_across_rooms_and_subjects(college, setup):
    admin = college["admin"]
    second_assignment = assign(admin, setup["cs102"]["id"], college["faculty"].membership_id)
    other_room = admin.post("/api/academic/rooms", {"name": "Room 2"}).json()
    assert schedule(admin, setup["assignment"]["id"], at(0, 9), at(0, 10), setup["room"]["id"]).status_code == 201
    clash = schedule(admin, second_assignment["id"], at(0, 9, 30), at(0, 11), other_room["id"])
    assert clash.status_code == 409 and clash.json()["code"] == "faculty_conflict"
    clash_no_room = schedule(admin, second_assignment["id"], at(0, 9, 59), at(0, 11))
    assert clash_no_room.json()["code"] == "faculty_conflict"


def test_cancelled_sessions_free_the_slot_and_are_frozen(college, setup):
    admin, room = college["admin"], setup["room"]["id"]
    first = schedule(admin, setup["assignment"]["id"], at(0, 9), at(0, 10), room).json()
    cancelled = admin.post(f"/api/academic/timetable/sessions/{first['id']}/cancel").json()
    assert cancelled["status"] == "cancelled"
    assert schedule(admin, setup["assignment"]["id"], at(0, 9), at(0, 10), room).status_code == 201
    r = admin.patch(f"/api/academic/timetable/sessions/{first['id']}", {"start_at": at(2, 9), "end_at": at(2, 10)})
    assert r.status_code == 409 and r.json()["code"] == "session_cancelled"


def test_modify_session(college, setup, make_client):
    admin = college["admin"]
    other = second_faculty(college, make_client)
    other_assignment = assign(admin, setup["cs102"]["id"], other.membership_id)
    first = schedule(admin, setup["assignment"]["id"], at(0, 9), at(0, 10), setup["room"]["id"]).json()
    second = schedule(admin, other_assignment["id"], at(0, 11), at(0, 12), setup["room"]["id"]).json()

    moved = admin.patch(f"/api/academic/timetable/sessions/{first['id']}", {"start_at": at(1, 9), "end_at": at(1, 10)})
    assert moved.status_code == 200 and moved.json()["start_at"].startswith("2027-01-05T09:00")
    # Only end_at moves: validated against the stored start.
    assert admin.patch(f"/api/academic/timetable/sessions/{first['id']}", {"end_at": at(1, 8)}).json()["code"] == "invalid_time_range"
    # Moving into another booking of the room is a conflict; the row itself does not conflict with its old slot.
    clash = admin.patch(f"/api/academic/timetable/sessions/{second['id']}", {"start_at": at(1, 9, 30), "end_at": at(1, 10, 30)})
    assert clash.json()["code"] == "room_conflict"
    assert admin.patch(f"/api/academic/timetable/sessions/{second['id']}", {"end_at": at(0, 12, 30)}).status_code == 200
    assert admin.patch(f"/api/academic/timetable/sessions/{second['id']}", {"room_id": None}).json()["room"] is None

    reassigned = admin.patch(f"/api/academic/timetable/sessions/{second['id']}", {"faculty_assignment_id": setup["assignment"]["id"]}).json()
    assert reassigned["subject"]["code"] == "CS101" and reassigned["faculty"]["full_name"] == "Ada Prof"
    for body in ({"course_id": setup["course"]["id"]}, {"status": "cancelled"}, {"start_at": None}):
        assert admin.patch(f"/api/academic/timetable/sessions/{second['id']}", body).status_code == 422


def test_session_references_validated(college, setup):
    admin = college["admin"]
    assert schedule(admin, str(uuid.uuid4()), at(0, 9), at(0, 10)).status_code == 404
    assert schedule(admin, setup["assignment"]["id"], at(0, 9), at(0, 10), str(uuid.uuid4())).status_code == 404
    admin.post(f"/api/academic/rooms/{setup['room']['id']}/archive")
    r = schedule(admin, setup["assignment"]["id"], at(0, 9), at(0, 10), setup["room"]["id"])
    assert r.status_code == 409 and r.json()["code"] == "room_archived"
    admin.post(f"/api/academic/subjects/{setup['cs101']['id']}/archive")
    assert schedule(admin, setup["assignment"]["id"], at(0, 9), at(0, 10)).json()["code"] == "subject_archived"


def test_database_enforces_course_subject_consistency(college, setup):
    aldermoor, a = college["aldermoor"], setup["assignment"]
    with session_factory()() as db:
        set_db_context(db, tenant_id=aldermoor.id)
        # A session whose subject differs from its assignment's.
        db.add(ClassSession(institution_id=aldermoor.id, faculty_assignment_id=uuid.UUID(a["id"]),
                            faculty_membership_id=college["faculty"].membership_id, course_id=uuid.UUID(setup["course"]["id"]),
                            subject_id=uuid.UUID(setup["cs102"]["id"]), start_at=MONDAY, end_at=MONDAY + timedelta(hours=1)))
        with pytest.raises(IntegrityError, match="fk_class_sessions_assignment_consistent"):
            db.flush()
        db.rollback()
        # An assignment whose subject is not in the stated course.
        other_course = create_course(college["admin"], code="BA-ENG")
        db.add(FacultyAssignment(institution_id=aldermoor.id, course_id=uuid.UUID(other_course["id"]), subject_id=uuid.UUID(setup["cs101"]["id"]),
                                 faculty_membership_id=college["faculty"].membership_id, academic_year="2026-27", academic_period="S1"))
        with pytest.raises(IntegrityError, match="fk_faculty_assignments_subject_in_course"):
            db.flush()


def test_database_rejects_overlaps_without_the_service(college, setup):
    """The exclusion constraint is the real guard (no check-then-insert race)."""
    aldermoor, a = college["aldermoor"], setup["assignment"]
    common = dict(institution_id=aldermoor.id, faculty_assignment_id=uuid.UUID(a["id"]), faculty_membership_id=college["faculty"].membership_id,
                  course_id=uuid.UUID(setup["course"]["id"]), subject_id=uuid.UUID(setup["cs101"]["id"]))
    with session_factory()() as db:
        set_db_context(db, tenant_id=aldermoor.id)
        db.add(ClassSession(**common, start_at=MONDAY, end_at=MONDAY + timedelta(hours=1)))
        db.flush()
        db.add(ClassSession(**common, start_at=MONDAY + timedelta(minutes=30), end_at=MONDAY + timedelta(hours=2)))
        with pytest.raises(IntegrityError, match="ex_class_sessions_faculty_overlap"):
            db.flush()


def test_only_admins_schedule(college, setup):
    for key in ("faculty", "student"):
        actor = college[key]
        assert schedule(actor, setup["assignment"]["id"], at(0, 9), at(0, 10)).status_code == 403
    s = schedule(college["admin"], setup["assignment"]["id"], at(0, 9), at(0, 10)).json()
    for key in ("faculty", "student"):
        actor = college[key]
        assert actor.patch(f"/api/academic/timetable/sessions/{s['id']}", {"end_at": at(0, 11)}).status_code == 403
        assert actor.post(f"/api/academic/timetable/sessions/{s['id']}/cancel").status_code == 403
        assert actor.get("/api/academic/timetable").status_code == 403


def test_no_physical_deletion(college, setup):
    with session_factory()() as db:
        set_db_context(db, tenant_id=college["aldermoor"].id)
        for table in ("rooms", "faculty_assignments", "class_sessions"):
            with pytest.raises(ProgrammingError, match="permission denied"):
                db.execute(text(f"DELETE FROM {table}"))
            db.rollback()


# ---- Timetable access ------------------------------------------------------


def test_student_timetable(college, setup, make_client):
    admin, student = college["admin"], college["student"]
    other = second_faculty(college, make_client)
    taught = schedule(admin, setup["assignment"]["id"], at(0, 9), at(0, 10), setup["room"]["id"]).json()
    # Same course, different period: not visible to a Semester 1 student.
    later = assign(admin, setup["cs102"]["id"], other.membership_id, period="Semester 2")
    hidden = schedule(admin, later["id"], at(1, 9), at(1, 10)).json()
    # Another course entirely.
    other_course = create_course(admin, code="BA-ENG")
    eng = create_subject(admin, other_course["id"], code="ENG1")
    unrelated = schedule(admin, assign(admin, eng["id"], other.membership_id)["id"], at(2, 9), at(2, 10)).json()

    week = student.get("/api/academic/timetable/me?week=2027-01-06").json()
    assert week["week_start"] == "2027-01-04" and week["week_end"] == "2027-01-11" and week["timezone"] == "UTC"
    assert [s["id"] for s in week["sessions"]] == [taught["id"]]
    assert student.get(f"/api/academic/timetable/sessions/{taught['id']}").status_code == 200
    for sid in (hidden["id"], unrelated["id"]):
        assert student.get(f"/api/academic/timetable/sessions/{sid}").status_code == 404

    # A classmate without an enrolment sees nothing; next week is empty.
    assert college["student2"].get("/api/academic/timetable/me?week=2027-01-04").json()["sessions"] == []
    assert student.get("/api/academic/timetable/me?week=2027-01-11").json()["sessions"] == []

    # Cancelled sessions stay visible (with status) unless excluded.
    admin.post(f"/api/academic/timetable/sessions/{taught['id']}/cancel")
    assert student.get("/api/academic/timetable/me?week=2027-01-04").json()["sessions"][0]["status"] == "cancelled"
    assert student.get("/api/academic/timetable/me?week=2027-01-04&include_cancelled=false").json()["sessions"] == []


def test_withdrawn_student_loses_timetable(college, setup):
    admin, student = college["admin"], college["student"]
    schedule(admin, setup["assignment"]["id"], at(0, 9), at(0, 10))
    enrolment = student.get("/api/academic/enrolments/me").json()[0]
    admin.patch(f"/api/academic/enrolments/{enrolment['id']}", {"status": "withdrawn"})
    assert student.get("/api/academic/timetable/me?week=2027-01-04").json()["sessions"] == []


def test_faculty_timetable_and_roster(college, setup, make_client):
    admin, faculty = college["admin"], college["faculty"]
    other = second_faculty(college, make_client)
    mine = schedule(admin, setup["assignment"]["id"], at(0, 9), at(0, 10)).json()
    theirs = schedule(admin, assign(admin, setup["cs102"]["id"], other.membership_id)["id"], at(0, 9), at(0, 10)).json()

    assert [s["id"] for s in faculty.get("/api/academic/timetable/me?week=2027-01-04").json()["sessions"]] == [mine["id"]]
    assert faculty.get(f"/api/academic/timetable/sessions/{theirs['id']}").status_code == 404

    # The assignment grants the matching enrolments: Maya (Semester 1), not a Semester 2 enrolment.
    enrol(admin, college["student2"].membership_id, setup["course"]["id"], period="Semester 2")
    roster = faculty.get(f"/api/academic/courses/{setup['course']['id']}/enrolments").json()
    assert [e["student"]["full_name"] for e in roster] == ["Maya Okafor"]
    assert [e["student"]["full_name"] for e in faculty.get("/api/academic/enrolments").json()] == ["Maya Okafor"]

    other_course = create_course(admin, code="BA-ENG")
    r = faculty.get(f"/api/academic/courses/{other_course['id']}/enrolments")
    assert r.status_code == 403 and r.json()["code"] == "not_assigned"
    # Ending the assignment removes the grant.
    admin.post(f"/api/academic/timetable/sessions/{mine['id']}/cancel")
    admin.post(f"/api/academic/faculty-assignments/{setup['assignment']['id']}/end")
    assert faculty.get("/api/academic/enrolments").json() == []


def test_admin_institution_timetable_filters(college, setup, make_client):
    admin = college["admin"]
    other = second_faculty(college, make_client)
    a = schedule(admin, setup["assignment"]["id"], at(0, 9), at(0, 10), setup["room"]["id"]).json()
    b = schedule(admin, assign(admin, setup["cs102"]["id"], other.membership_id)["id"], at(3, 14), at(3, 15)).json()
    all_ids = [s["id"] for s in admin.get("/api/academic/timetable?week=2027-01-04").json()["sessions"]]
    assert all_ids == [a["id"], b["id"]]  # ordered by start
    by_room = admin.get(f"/api/academic/timetable?week=2027-01-04&room_id={setup['room']['id']}").json()["sessions"]
    assert [s["id"] for s in by_room] == [a["id"]]
    by_faculty = admin.get(f"/api/academic/timetable?week=2027-01-04&faculty_membership_id={other.membership_id}").json()["sessions"]
    assert [s["id"] for s in by_faculty] == [b["id"]]


def _set_timezone(institution, tz: str) -> None:
    with session_factory()() as db:
        db.execute(update(Institution).where(Institution.id == institution.id).values(timezone=tz))
        db.commit()


def test_week_uses_institution_timezone(college, setup):
    _set_timezone(college["aldermoor"], "Asia/Kolkata")
    admin = college["admin"]
    # Sunday 20:00 UTC = Monday 01:30 IST: belongs to the IST week of 4 January.
    early = schedule(admin, setup["assignment"]["id"], "2027-01-03T20:00:00Z", "2027-01-03T21:00:00Z").json()
    # Sunday 19:00 UTC = 00:30 IST next Monday: belongs to the following week.
    late = schedule(admin, setup["assignment"]["id"], "2027-01-10T19:00:00Z", "2027-01-10T20:00:00Z").json()
    week = admin.get("/api/academic/timetable?week=2027-01-04").json()
    assert week["timezone"] == "Asia/Kolkata"
    assert week["starts_at"] == "2027-01-04T00:00:00+05:30" and week["ends_at"] == "2027-01-11T00:00:00+05:30"
    assert [s["id"] for s in week["sessions"]] == [early["id"]]
    assert [s["id"] for s in admin.get("/api/academic/timetable?week=2027-01-11").json()["sessions"]] == [late["id"]]


def test_week_across_dst_change(college):
    _set_timezone(college["aldermoor"], "Europe/London")
    week = college["admin"].get("/api/academic/timetable?week=2027-03-24").json()  # DST starts Sun 28 March 2027
    assert week["starts_at"] == "2027-03-22T00:00:00Z" and week["ends_at"] == "2027-03-29T00:00:00+01:00"
    start = datetime.fromisoformat(week["starts_at"])
    end = datetime.fromisoformat(week["ends_at"])
    assert end - start == timedelta(hours=167)


def test_platform_admin_sets_valid_timezone(college, make_client):
    make_user("root@platform.example", [], platform_admin=True)
    from tests.helpers import Actor, login

    c = make_client(client_host="10.250.0.1")
    operator = Actor(c, login(c, "root@platform.example"), None)
    assert operator.patch("/api/platform/institutions/aldermoor", {"timezone": "Mars/Olympus"}).status_code == 422
    assert operator.patch("/api/platform/institutions/aldermoor", {"timezone": "Asia/Kolkata"}).json()["timezone"] == "Asia/Kolkata"
    assert college["admin"].patch("/api/platform/institutions/aldermoor", {"timezone": "UTC"}).status_code == 403


# ---- Tenant isolation ------------------------------------------------------


def test_cross_institution_references_rejected(college, setup):
    other_admin = college["other_admin"]
    foreign_course = create_course(other_admin, code="HAL-1")
    foreign_subject = create_subject(other_admin, foreign_course["id"], code="H1")
    foreign_room = other_admin.post("/api/academic/rooms", {"name": "Hall"}).json()
    admin = college["admin"]

    # Aldermoor cannot use Halvard's subject, room or people.
    body = {"academic_year": "2026-27", "academic_period": "S1"}
    r = admin.post("/api/academic/faculty-assignments", {**body, "subject_id": foreign_subject["id"], "faculty_membership_id": str(college["faculty"].membership_id)})
    assert r.status_code == 404
    r = other_admin.post("/api/academic/faculty-assignments", {**body, "subject_id": foreign_subject["id"], "faculty_membership_id": str(college["faculty"].membership_id)})
    assert r.status_code == 404 and r.json()["code"] == "faculty_not_found"
    assert schedule(admin, setup["assignment"]["id"], at(0, 9), at(0, 10), foreign_room["id"]).status_code == 404
    assert schedule(other_admin, setup["assignment"]["id"], at(0, 9), at(0, 10)).status_code == 404


def test_other_institution_cannot_see_or_change_schedule(college, setup):
    s = schedule(college["admin"], setup["assignment"]["id"], at(0, 9), at(0, 10), setup["room"]["id"]).json()
    other = college["other_admin"]
    assert other.get("/api/academic/timetable?week=2027-01-04").json()["sessions"] == []
    assert other.get("/api/academic/rooms").json() == []
    assert other.get("/api/academic/faculty-assignments").json() == []
    checks = [
        other.get(f"/api/academic/timetable/sessions/{s['id']}"),
        other.patch(f"/api/academic/timetable/sessions/{s['id']}", {"end_at": at(0, 11)}),
        other.post(f"/api/academic/timetable/sessions/{s['id']}/cancel"),
        other.get(f"/api/academic/rooms/{setup['room']['id']}"),
        other.post(f"/api/academic/rooms/{setup['room']['id']}/archive"),
        other.get(f"/api/academic/faculty-assignments/{setup['assignment']['id']}"),
        other.post(f"/api/academic/faculty-assignments/{setup['assignment']['id']}/end"),
    ]
    assert [r.status_code for r in checks] == [404] * len(checks)
    assert college["other_student"].get("/api/academic/timetable/me?week=2027-01-04").json()["sessions"] == []


def test_rls_isolates_timetable_tables(college, setup):
    schedule(college["admin"], setup["assignment"]["id"], at(0, 9), at(0, 10), setup["room"]["id"])
    with session_factory()() as db:
        for tenant, expected in ((college["aldermoor"].id, 1), (college["halvard"].id, 0), (None, 0)):
            set_db_context(db, tenant_id=tenant)
            for model in (Room, FacultyAssignment, ClassSession):
                assert db.scalar(select(func.count()).select_from(model)) == expected, (model, tenant)
        set_db_context(db, tenant_id=college["aldermoor"].id)
        db.add(Room(institution_id=college["halvard"].id, name="Sneaky"))
        with pytest.raises(ProgrammingError, match="row-level security"):
            db.flush()
