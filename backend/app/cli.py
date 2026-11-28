"""Operator commands. Privileged accounts are created here, never via the API.

    python -m app.cli create-platform-admin --email ops@example.org --name "Ops"
    python -m app.cli seed-demo
    python -m app.cli seed-academic-demo    # courses, enrolments, timetable (after seed-demo)
    python -m app.cli purge-rate-limits
    python -m app.cli dev-mail              # show the newest development email

Passwords are read from OPENCAMPUS_CLI_PASSWORD if set, otherwise prompted.
"""

import argparse
import getpass
import os
import sys
import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.db.session import session_factory, set_db_context
from app.models import Institution, Membership, MembershipRole, MembershipStatus, PublicationStatus, User
from app.schemas.auth import PASSWORD_MAX, PASSWORD_MIN
from app.services.auth import normalise_email


def _password() -> str:
    password = os.getenv("OPENCAMPUS_CLI_PASSWORD") or getpass.getpass("Password: ")
    if not PASSWORD_MIN <= len(password) <= PASSWORD_MAX:
        sys.exit(f"Password must be {PASSWORD_MIN}-{PASSWORD_MAX} characters")
    return password


def _get_or_create_user(db: Session, email: str, name: str, password_hash: str) -> User:
    user = db.scalar(select(User).where(User.email == normalise_email(email)))
    if user is None:
        user = User(email=normalise_email(email), full_name=name, password_hash=password_hash)
        db.add(user)
        db.flush()
    return user


def _ensure_membership(db: Session, user: User, institution: Institution, role: MembershipRole) -> None:
    set_db_context(db, tenant_id=institution.id)
    membership = db.scalar(
        select(Membership).where(Membership.institution_id == institution.id, Membership.user_id == user.id)
    )
    if membership is None:
        db.add(Membership(institution_id=institution.id, user_id=user.id, role=role, status=MembershipStatus.active))
        db.flush()
    set_db_context(db)


def create_platform_admin(email: str, name: str) -> None:
    with session_factory()() as db:
        user = _get_or_create_user(db, email, name, hash_password(_password()))
        user.is_platform_admin = True
        db.commit()
        print(f"Platform admin ready: {user.email}")


# Fictional demo data: reserved .example domains, invented names.
DEMO_INSTITUTIONS = [("aldermoor", "Aldermoor College"), ("halvard", "Halvard Institute of Technology")]
DEMO_USERS = [
    ("maya.okafor@aldermoor.example", "Maya Okafor", [("aldermoor", MembershipRole.student)]),
    ("lena.varga@aldermoor.example", "Lena Varga", [("aldermoor", MembershipRole.faculty)]),
    ("iris.moreau@aldermoor.example", "Iris Moreau", [("aldermoor", MembershipRole.college_admin)]),
    ("tomas.berg@halvard.example", "Tomas Berg", [("halvard", MembershipRole.student)]),
    (
        "sam.achebe@aldermoor.example",
        "Samuel Achebe",
        [("aldermoor", MembershipRole.faculty), ("halvard", MembershipRole.student)],
    ),
]


def seed_demo() -> None:
    password_hash = hash_password(_password())
    with session_factory()() as db:
        institutions: dict[str, Institution] = {}
        for slug, name in DEMO_INSTITUTIONS:
            institution = db.scalar(select(Institution).where(Institution.slug == slug))
            if institution is None:
                institution = Institution(slug=slug, name=name, allow_self_registration=True)
                db.add(institution)
                db.flush()
            institutions[slug] = institution

        for email, name, memberships in DEMO_USERS:
            user = _get_or_create_user(db, email, name, password_hash)
            for slug, role in memberships:
                _ensure_membership(db, user, institutions[slug], role)
        db.commit()

    print("Demo data ready (all accounts share the password you entered):")
    for email, _, memberships in DEMO_USERS:
        print(f"  {email:34} " + ", ".join(f"{role.value}@{slug}" for slug, role in memberships))


def seed_academic_demo(weeks: int = 4) -> None:
    """Fictional academic records for Aldermoor, created through the real
    services (so every validation applies). Safe to re-run: existing rows are
    reused and already-booked sessions are skipped."""
    from datetime import datetime, time, timedelta

    from app.core.errors import ApiError
    from app.models import ClassSession, Course, Enrolment, FacultyAssignment, Room, Subject
    from app.schemas.academic import AssignmentCreate, CourseCreate, EnrolmentCreate, RoomCreate, SessionCreate, SubjectCreate
    from app.services.academic import courses, enrolments, timetable

    year, period = "2026-27", "Semester 1"
    with session_factory()() as db:
        institution = db.scalar(select(Institution).where(Institution.slug == "aldermoor"))
        if institution is None:
            sys.exit("Run seed-demo first (Aldermoor College not found)")
        iid = institution.id
        set_db_context(db, tenant_id=iid)

        def member(email: str) -> Membership:
            return db.scalar(
                select(Membership).join(User, User.id == Membership.user_id).where(Membership.institution_id == iid, User.email == email)
            )

        course = db.scalar(select(Course).where(Course.institution_id == iid, Course.code == "BSC-CS"))
        if course is None:
            course = courses.create_course(db, iid, CourseCreate(
                name="B.Sc. Computer Science", code="BSC-CS", degree_level="bachelor", duration_semesters=6,
                description="Three-year undergraduate programme in computing."))
        if not db.scalar(select(Course.id).where(Course.institution_id == iid, Course.code == "BA-ENG")):
            courses.create_course(db, iid, CourseCreate(
                name="B.A. English Literature", code="BA-ENG", degree_level="bachelor", duration_semesters=6))

        subjects = {}
        for code, name, semester, credits in [
            ("CS101", "Programming Fundamentals", 1, 4), ("CS102", "Discrete Mathematics", 1, 3),
            ("CS103", "Computer Systems", 1, 3), ("CS201", "Data Structures", 2, 4),
        ]:
            subject = db.scalar(select(Subject).where(Subject.institution_id == iid, Subject.course_id == course.id, Subject.code == code))
            subjects[code] = subject or courses.create_subject(
                db, iid, course.id, SubjectCreate(name=name, code=code, semester=semester, credits=credits))

        rooms = {}
        for name, building, capacity in [("Lab 1", "Turing Building", 40), ("Lecture Hall A", "Main Building", 120)]:
            room = db.scalar(select(Room).where(Room.institution_id == iid, Room.name == name, Room.building == building))
            rooms[name] = room or timetable.create_room(db, iid, RoomCreate(name=name, building=building, capacity=capacity))

        def assignment(code: str, email: str) -> uuid.UUID:
            faculty = member(email)
            existing = db.scalar(select(FacultyAssignment.id).where(
                FacultyAssignment.institution_id == iid, FacultyAssignment.subject_id == subjects[code].id,
                FacultyAssignment.faculty_membership_id == faculty.id, FacultyAssignment.status == "active"))
            return existing or timetable.create_assignment(db, iid, AssignmentCreate(
                subject_id=subjects[code].id, faculty_membership_id=faculty.id, academic_year=year, academic_period=period)).id

        lena, sam = "lena.varga@aldermoor.example", "sam.achebe@aldermoor.example"
        plan = {  # weekday -> (start, minutes, subject, faculty, room)
            0: [(time(9), 90, "CS101", lena, "Lecture Hall A"), (time(14), 120, "CS103", sam, "Lab 1")],
            1: [(time(10), 60, "CS102", sam, "Lecture Hall A")],
            2: [(time(9), 120, "CS101", lena, "Lab 1"), (time(13), 60, "CS102", sam, "Lecture Hall A")],
            3: [(time(11), 90, "CS103", sam, "Lecture Hall A")],
            4: [(time(9, 30), 60, "CS101", lena, "Lecture Hall A"), (time(11), 60, "CS102", sam, None)],
        }
        ids = {(code, email): assignment(code, email) for day in plan.values() for _, _, code, email, _ in day}

        maya = member("maya.okafor@aldermoor.example")
        if not db.scalar(select(Enrolment.id).where(Enrolment.institution_id == iid, Enrolment.student_membership_id == maya.id,
                                                    Enrolment.course_id == course.id, Enrolment.status == "active")):
            enrolments.create_enrolment(db, iid, EnrolmentCreate(
                student_membership_id=maya.id, course_id=course.id, academic_year=year, academic_period=period))

        zone = timetable.institution_zone(institution)
        _, monday, _ = timetable.week_window(zone, None)
        created = 0
        for week in range(weeks):
            for weekday, slots in plan.items():
                day = (monday + timedelta(days=7 * week + weekday)).date()
                for start, minutes, code, email, room in slots:
                    start_at = datetime.combine(day, start, tzinfo=zone)
                    try:
                        set_db_context(db, tenant_id=iid)
                        timetable.create_session(db, iid, SessionCreate(
                            faculty_assignment_id=ids[(code, email)], room_id=rooms[room].id if room else None,
                            start_at=start_at, end_at=start_at + timedelta(minutes=minutes)))
                        created += 1
                    except ApiError as exc:
                        if exc.code not in ("room_conflict", "faculty_conflict"):
                            raise
        set_db_context(db, tenant_id=iid)
        total = db.scalar(select(func.count()).select_from(ClassSession).where(ClassSession.institution_id == iid))
        _seed_content(db, institution, member, subjects, course)
    print(f"Academic demo data ready for Aldermoor ({zone.key}): {created} new sessions, {total} in total.")


def _seed_content(db: Session, institution: Institution, member, subjects: dict, course) -> None:
    """Resources, an assignment and announcements (M4.4-M4.6), authored
    through the services as the people who would write them. Skips any title
    that already exists."""
    from datetime import timedelta

    from app.api.deps import TenantContext
    from app.core.security import utcnow
    from app.models import Announcement, Assignment, LearningResource, User
    from app.schemas.academic import AnnouncementCreate, AssignmentWorkCreate, ResourceCreate
    from app.services.academic import announcements, coursework, resources

    iid = institution.id

    def as_member(email: str) -> TenantContext:
        membership = member(email)
        set_db_context(db, tenant_id=iid, user_id=membership.user_id)
        return TenantContext(db.get(User, membership.user_id), None, institution, membership)

    def exists(model, title: str) -> bool:
        set_db_context(db, tenant_id=iid)
        return bool(db.scalar(select(model.id).where(model.institution_id == iid, model.title == title)))

    lena = as_member("lena.varga@aldermoor.example")
    cs101 = subjects["CS101"].id
    for item in [
        dict(title="Week 1: values, variables and types", resource_type="note", topic="Week 1",
             body="A variable names a value.\nEvery value has a type that decides what you can do with it."),
        dict(title="The Python tutorial", resource_type="link", topic="Week 1",
             external_url="https://docs.python.org/3/tutorial/", description="Chapters 1-3 before Wednesday."),
    ]:
        if not exists(LearningResource, item["title"]):
            r = resources.create(db, lena, cs101, ResourceCreate(**item))
            resources.set_status(db, as_member("lena.varga@aldermoor.example"), r.id, PublicationStatus.published)

    title = "Problem set 1: expressions"
    if not exists(Assignment, title):
        now = utcnow()
        a = coursework.create(db, as_member("lena.varga@aldermoor.example"), cs101, AssignmentWorkCreate(
            title=title, instructions="Answer questions 1-5 from the week 1 notes. Show your working.",
            available_from=now - timedelta(days=1), due_at=now + timedelta(days=6), late_policy="accept", max_marks=20))
        coursework.set_status(db, as_member("lena.varga@aldermoor.example"), a.id, PublicationStatus.published)

    for email, data in [
        ("iris.moreau@aldermoor.example", AnnouncementCreate(title="Library opens late during exams", body="From next week the library is open until 22:00.", audience="institution", priority="important")),
        ("lena.varga@aldermoor.example", AnnouncementCreate(title="CS101 Wednesday lab moves to Lab 1", body="Same time, Turing Building.", audience="subject", subject_id=cs101)),
    ]:
        if not exists(Announcement, data.title):
            created = announcements.create(db, as_member(email), data)
            announcements.set_status(db, as_member(email), created.id, PublicationStatus.published)


def main() -> None:
    parser = argparse.ArgumentParser(prog="python -m app.cli")
    commands = parser.add_subparsers(dest="command", required=True)
    admin = commands.add_parser("create-platform-admin", help="create or promote a platform administrator")
    admin.add_argument("--email", required=True)
    admin.add_argument("--name", required=True)
    commands.add_parser("seed-demo", help="create fictional demo institutions and users")
    commands.add_parser("seed-academic-demo", help="create fictional courses, enrolments and a timetable (Aldermoor)")
    commands.add_parser("purge-rate-limits", help="delete expired rate-limit counters")
    commands.add_parser("dev-mail", help="print the newest email from the development sink")
    args = parser.parse_args()

    if args.command == "create-platform-admin":
        create_platform_admin(args.email, args.name)
    elif args.command == "dev-mail":
        from app.core.config import get_settings

        settings = get_settings()
        files = sorted(settings.email_dev_dir.glob("*.eml")) if settings.email_dev_dir.is_dir() else []
        if not files:
            sys.exit(f"No development emails in {settings.email_dev_dir}")
        print(f"# {files[-1]}\n")
        print(files[-1].read_text())
    elif args.command == "purge-rate-limits":
        from app.core.config import get_settings
        from app.services.rate_limit import get_rate_limiter

        print(f"Deleted {get_rate_limiter(get_settings()).purge_expired()} expired rate-limit counters")
    elif args.command == "seed-academic-demo":
        seed_academic_demo()
    else:
        seed_demo()


if __name__ == "__main__":
    main()
