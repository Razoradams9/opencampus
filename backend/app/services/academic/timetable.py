"""Rooms, faculty assignments, class sessions and timetable queries (M4.3).

Visibility of sessions:
  college_admin  every session in the institution (GET /timetable)
  faculty        sessions of their own faculty membership
  student        sessions whose course, academic year and period match one of
                 their *active* enrolments
Overlaps are rejected by exclusion constraints in PostgreSQL; this module
validates references and lifecycle, then maps constraint names to errors.
"""

import uuid
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import Select, and_, exists, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, aliased

from app.api.deps import TenantContext
from app.core.errors import ApiError, forbidden
from app.core.security import utcnow
from app.models import (
    AcademicStatus,
    AssignmentStatus,
    ClassSession,
    Course,
    Enrolment,
    EnrolmentStatus,
    FacultyAssignment,
    Institution,
    Membership,
    MembershipRole,
    MembershipStatus,
    Room,
    SessionStatus,
    Subject,
    User,
)
from app.models.timetable import MAX_SESSION_HOURS
from app.schemas.academic import (
    AssignmentCreate,
    AssignmentOut,
    CourseRef,
    RoomCreate,
    RoomRef,
    RoomUpdate,
    SessionCreate,
    SessionOut,
    SessionUpdate,
    SubjectRef,
    TeacherRef,
    TimetableWeek,
)
from app.services.academic.common import conflict, constraint_name, not_found

DEFAULT_TIMEZONE = "UTC"

_CONSTRAINT_ERRORS = {
    "uq_rooms_institution_building_name": (409, "room_exists", "A room with this name already exists in this building"),
    "uq_faculty_assignments_active": (
        409, "assignment_exists", "This faculty member is already assigned to this subject for this period",
    ),
    "ex_class_sessions_room_overlap": (409, "room_conflict", "The room is already booked for an overlapping time"),
    "ex_class_sessions_faculty_overlap": (
        409, "faculty_conflict", "The faculty member already teaches another session at an overlapping time",
    ),
    "ck_class_sessions_ends_after_start": (422, "invalid_time_range", "A session must end after it starts"),
    "ck_class_sessions_max_duration": (
        422, "invalid_time_range", f"A session cannot be longer than {MAX_SESSION_HOURS} hours",
    ),
}


def _flush(db: Session) -> None:
    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        known = _CONSTRAINT_ERRORS.get(constraint_name(exc) or "")
        if known:
            raise ApiError(*known) from None
        raise


def institution_zone(institution: Institution) -> ZoneInfo:
    try:
        return ZoneInfo(institution.timezone or DEFAULT_TIMEZONE)
    except (ZoneInfoNotFoundError, ValueError):
        return ZoneInfo(DEFAULT_TIMEZONE)


# ---- Rooms -----------------------------------------------------------------


def list_rooms(db: Session, institution_id: uuid.UUID, status: AcademicStatus | None) -> list[Room]:
    query = select(Room).where(Room.institution_id == institution_id)
    if status is not None:
        query = query.where(Room.status == status)
    return list(db.scalars(query.order_by(Room.building, Room.name)))


def _room(db: Session, institution_id: uuid.UUID, room_id: uuid.UUID, *, lock: bool = False) -> Room:
    query = select(Room).where(Room.institution_id == institution_id, Room.id == room_id)
    room = db.scalar(query.with_for_update() if lock else query)
    if room is None:
        raise not_found("room", "Room")
    return room


def get_room(db: Session, institution_id: uuid.UUID, room_id: uuid.UUID, *, active_only: bool) -> Room:
    room = _room(db, institution_id, room_id)
    if active_only and room.status != AcademicStatus.active:
        raise not_found("room", "Room")
    return room


def create_room(db: Session, institution_id: uuid.UUID, data: RoomCreate) -> Room:
    room = Room(institution_id=institution_id, **data.model_dump())
    db.add(room)
    _flush(db)
    db.commit()
    return room


def update_room(db: Session, institution_id: uuid.UUID, room_id: uuid.UUID, data: RoomUpdate) -> Room:
    room = _room(db, institution_id, room_id, lock=True)
    for name, value in data.changes().items():
        setattr(room, name, value)
    _flush(db)
    db.commit()
    return room


def _future_sessions(db: Session, institution_id: uuid.UUID, *conditions) -> int:
    return db.scalar(
        select(func.count())
        .select_from(ClassSession)
        .where(
            ClassSession.institution_id == institution_id,
            ClassSession.status == SessionStatus.scheduled,
            ClassSession.end_at > utcnow(),
            *conditions,
        )
    )


def set_room_status(db: Session, institution_id: uuid.UUID, room_id: uuid.UUID, status: AcademicStatus) -> Room:
    room = _room(db, institution_id, room_id, lock=True)
    if status == AcademicStatus.archived:
        pending = _future_sessions(db, institution_id, ClassSession.room_id == room.id)
        if pending:
            raise conflict("room_has_sessions", f"{pending} upcoming session(s) use this room; move or cancel them first")
    room.status = status
    db.flush()
    db.commit()
    return room


# ---- Faculty assignments ---------------------------------------------------

Teacher = aliased(Membership, name="teacher")


def _assignment_base(institution_id: uuid.UUID) -> Select:
    return (
        select(FacultyAssignment, Course, Subject, Teacher.id, User.full_name)
        .join(Course, and_(Course.institution_id == FacultyAssignment.institution_id, Course.id == FacultyAssignment.course_id))
        .join(Subject, and_(Subject.institution_id == FacultyAssignment.institution_id, Subject.id == FacultyAssignment.subject_id))
        .join(
            Teacher,
            and_(Teacher.institution_id == FacultyAssignment.institution_id, Teacher.id == FacultyAssignment.faculty_membership_id),
        )
        .join(User, User.id == Teacher.user_id)
        .where(FacultyAssignment.institution_id == institution_id)
    )


def _course_ref(course: Course) -> CourseRef:
    return CourseRef(id=course.id, name=course.name, code=course.code, status=course.status)


def _subject_ref(subject: Subject) -> SubjectRef:
    return SubjectRef(id=subject.id, name=subject.name, code=subject.code, semester=subject.semester, credits=float(subject.credits))


def _assignment_out(row) -> AssignmentOut:
    assignment, course, subject, teacher_id, teacher_name = row
    return AssignmentOut(
        id=assignment.id,
        course=_course_ref(course),
        subject=_subject_ref(subject),
        faculty=TeacherRef(membership_id=teacher_id, full_name=teacher_name),
        academic_year=assignment.academic_year,
        academic_period=assignment.academic_period,
        status=assignment.status,
        created_at=assignment.created_at,
        updated_at=assignment.updated_at,
    )


@dataclass
class AssignmentFilters:
    course_id: uuid.UUID | None = None
    subject_id: uuid.UUID | None = None
    faculty_membership_id: uuid.UUID | None = None
    status: AssignmentStatus | None = None
    academic_year: str | None = None


def _assignment_scope(query: Select, tenant: TenantContext) -> Select:
    if tenant.role == MembershipRole.college_admin:
        return query
    if tenant.role == MembershipRole.faculty:
        return query.where(FacultyAssignment.faculty_membership_id == tenant.membership.id)
    raise forbidden("insufficient_role", "Your role does not allow access to teaching assignments")


def list_assignments(db: Session, tenant: TenantContext, filters: AssignmentFilters, *, limit: int, offset: int) -> list[AssignmentOut]:
    query = _assignment_scope(_assignment_base(tenant.institution_id), tenant)
    for column, value in (
        (FacultyAssignment.course_id, filters.course_id),
        (FacultyAssignment.subject_id, filters.subject_id),
        (FacultyAssignment.faculty_membership_id, filters.faculty_membership_id),
        (FacultyAssignment.status, filters.status),
        (FacultyAssignment.academic_year, filters.academic_year),
    ):
        if value is not None:
            query = query.where(column == value)
    query = query.order_by(FacultyAssignment.academic_year.desc(), Course.code, Subject.semester, Subject.code, User.full_name)
    return [_assignment_out(row) for row in db.execute(query.limit(limit).offset(offset))]


def my_assignments(db: Session, tenant: TenantContext, status: AssignmentStatus | None) -> list[AssignmentOut]:
    query = _assignment_base(tenant.institution_id).where(FacultyAssignment.faculty_membership_id == tenant.membership.id)
    if status is not None:
        query = query.where(FacultyAssignment.status == status)
    query = query.order_by(FacultyAssignment.academic_year.desc(), Course.code, Subject.semester, Subject.code)
    return [_assignment_out(row) for row in db.execute(query)]


def get_assignment(db: Session, tenant: TenantContext, assignment_id: uuid.UUID) -> AssignmentOut:
    try:
        query = _assignment_scope(_assignment_base(tenant.institution_id), tenant)
    except ApiError:
        raise not_found("assignment", "Assignment") from None
    row = db.execute(query.where(FacultyAssignment.id == assignment_id)).one_or_none()
    if row is None:
        raise not_found("assignment", "Assignment")
    return _assignment_out(row)


def _active_faculty(db: Session, institution_id: uuid.UUID, membership_id: uuid.UUID) -> Membership:
    membership = db.scalar(
        select(Membership)
        .where(Membership.institution_id == institution_id, Membership.id == membership_id)
        .with_for_update(read=True, of=Membership)
    )
    if membership is None:
        raise not_found("faculty", "Faculty member")
    if membership.role != MembershipRole.faculty or membership.status != MembershipStatus.active:
        raise conflict("not_an_active_faculty", "Only active faculty members can teach")
    return membership


def _active_subject_and_course(db: Session, institution_id: uuid.UUID, subject_id: uuid.UUID) -> tuple[Subject, Course]:
    row = db.execute(
        select(Subject, Course)
        .join(Course, and_(Course.institution_id == Subject.institution_id, Course.id == Subject.course_id))
        .where(Subject.institution_id == institution_id, Subject.id == subject_id)
        .with_for_update(read=True, of=(Subject, Course))
    ).one_or_none()
    if row is None:
        raise not_found("subject", "Subject")
    subject, course = row
    if subject.status != AcademicStatus.active or course.status != AcademicStatus.active:
        raise conflict("subject_archived", "The subject or its course is archived")
    return subject, course


def create_assignment(db: Session, institution_id: uuid.UUID, data: AssignmentCreate) -> AssignmentOut:
    subject, course = _active_subject_and_course(db, institution_id, data.subject_id)
    _active_faculty(db, institution_id, data.faculty_membership_id)
    assignment = FacultyAssignment(
        institution_id=institution_id,
        course_id=course.id,
        subject_id=subject.id,
        faculty_membership_id=data.faculty_membership_id,
        academic_year=data.academic_year,
        academic_period=data.academic_period,
    )
    db.add(assignment)
    _flush(db)
    db.commit()
    return get_assignment_admin(db, institution_id, assignment.id)


def get_assignment_admin(db: Session, institution_id: uuid.UUID, assignment_id: uuid.UUID) -> AssignmentOut:
    row = db.execute(_assignment_base(institution_id).where(FacultyAssignment.id == assignment_id)).one_or_none()
    if row is None:
        raise not_found("assignment", "Assignment")
    return _assignment_out(row)


def end_assignment(db: Session, institution_id: uuid.UUID, assignment_id: uuid.UUID) -> AssignmentOut:
    assignment = db.scalar(
        select(FacultyAssignment)
        .where(FacultyAssignment.institution_id == institution_id, FacultyAssignment.id == assignment_id)
        .with_for_update()
    )
    if assignment is None:
        raise not_found("assignment", "Assignment")
    if assignment.status == AssignmentStatus.active:
        pending = _future_sessions(db, institution_id, ClassSession.faculty_assignment_id == assignment.id)
        if pending:
            raise conflict(
                "assignment_has_sessions", f"{pending} upcoming session(s) use this assignment; reassign or cancel them first"
            )
        assignment.status = AssignmentStatus.ended
        db.flush()
        db.commit()
    return get_assignment_admin(db, institution_id, assignment.id)


# ---- Sessions --------------------------------------------------------------


def _session_base(institution_id: uuid.UUID) -> Select:
    return (
        select(ClassSession, FacultyAssignment, Course, Subject, Teacher.id, User.full_name, Room)
        .join(
            FacultyAssignment,
            and_(
                FacultyAssignment.institution_id == ClassSession.institution_id,
                FacultyAssignment.id == ClassSession.faculty_assignment_id,
            ),
        )
        .join(Course, and_(Course.institution_id == ClassSession.institution_id, Course.id == ClassSession.course_id))
        .join(Subject, and_(Subject.institution_id == ClassSession.institution_id, Subject.id == ClassSession.subject_id))
        .join(
            Teacher,
            and_(Teacher.institution_id == ClassSession.institution_id, Teacher.id == ClassSession.faculty_membership_id),
        )
        .join(User, User.id == Teacher.user_id)
        .outerjoin(Room, and_(Room.institution_id == ClassSession.institution_id, Room.id == ClassSession.room_id))
        .where(ClassSession.institution_id == institution_id)
    )


def _session_out(row) -> SessionOut:
    session, assignment, course, subject, teacher_id, teacher_name, room = row
    return SessionOut(
        id=session.id,
        start_at=session.start_at,
        end_at=session.end_at,
        status=session.status,
        course=_course_ref(course),
        subject=_subject_ref(subject),
        faculty=TeacherRef(membership_id=teacher_id, full_name=teacher_name),
        room=RoomRef(id=room.id, name=room.name, building=room.building) if room else None,
        faculty_assignment_id=assignment.id,
        academic_year=assignment.academic_year,
        academic_period=assignment.academic_period,
        created_at=session.created_at,
        updated_at=session.updated_at,
    )


def _personal_condition(membership_id: uuid.UUID):
    """Sessions a member teaches, or attends through an active enrolment whose
    course, academic year and period match the session's assignment."""
    attends = exists().where(
        Enrolment.institution_id == ClassSession.institution_id,
        Enrolment.student_membership_id == membership_id,
        Enrolment.status == EnrolmentStatus.active,
        Enrolment.course_id == ClassSession.course_id,
        Enrolment.academic_year == FacultyAssignment.academic_year,
        Enrolment.academic_period == FacultyAssignment.academic_period,
    )
    return or_(ClassSession.faculty_membership_id == membership_id, attends)


def get_session(db: Session, tenant: TenantContext, session_id: uuid.UUID) -> SessionOut:
    query = _session_base(tenant.institution_id).where(ClassSession.id == session_id)
    if tenant.role != MembershipRole.college_admin:
        query = query.where(_personal_condition(tenant.membership.id))
    row = db.execute(query).one_or_none()
    if row is None:
        raise not_found("session", "Session")
    return _session_out(row)


def _validate_times(start_at: datetime, end_at: datetime) -> None:
    if end_at <= start_at:
        raise ApiError(422, "invalid_time_range", "A session must end after it starts")
    if end_at - start_at > timedelta(hours=MAX_SESSION_HOURS):
        raise ApiError(422, "invalid_time_range", f"A session cannot be longer than {MAX_SESSION_HOURS} hours")


def _usable_assignment(db: Session, institution_id: uuid.UUID, assignment_id: uuid.UUID) -> FacultyAssignment:
    assignment = db.scalar(
        select(FacultyAssignment)
        .where(FacultyAssignment.institution_id == institution_id, FacultyAssignment.id == assignment_id)
        .with_for_update(read=True)
    )
    if assignment is None:
        raise not_found("assignment", "Assignment")
    if assignment.status != AssignmentStatus.active:
        raise conflict("assignment_ended", "This teaching assignment has ended")
    _active_faculty(db, institution_id, assignment.faculty_membership_id)
    _active_subject_and_course(db, institution_id, assignment.subject_id)
    return assignment


def _usable_room(db: Session, institution_id: uuid.UUID, room_id: uuid.UUID) -> Room:
    room = db.scalar(
        select(Room).where(Room.institution_id == institution_id, Room.id == room_id).with_for_update(read=True)
    )
    if room is None:
        raise not_found("room", "Room")
    if room.status != AcademicStatus.active:
        raise conflict("room_archived", "This room is archived")
    return room


def _reload_session(db: Session, institution_id: uuid.UUID, session_id: uuid.UUID) -> SessionOut:
    return _session_out(db.execute(_session_base(institution_id).where(ClassSession.id == session_id)).one())


def create_session(db: Session, institution_id: uuid.UUID, data: SessionCreate) -> SessionOut:
    _validate_times(data.start_at, data.end_at)
    assignment = _usable_assignment(db, institution_id, data.faculty_assignment_id)
    if data.room_id is not None:
        _usable_room(db, institution_id, data.room_id)
    session = ClassSession(
        institution_id=institution_id,
        faculty_assignment_id=assignment.id,
        faculty_membership_id=assignment.faculty_membership_id,
        course_id=assignment.course_id,
        subject_id=assignment.subject_id,
        room_id=data.room_id,
        start_at=data.start_at,
        end_at=data.end_at,
    )
    db.add(session)
    _flush(db)
    db.commit()
    return _reload_session(db, institution_id, session.id)


def _locked_session(db: Session, institution_id: uuid.UUID, session_id: uuid.UUID) -> ClassSession:
    session = db.scalar(
        select(ClassSession).where(ClassSession.institution_id == institution_id, ClassSession.id == session_id).with_for_update()
    )
    if session is None:
        raise not_found("session", "Session")
    return session


def update_session(db: Session, institution_id: uuid.UUID, session_id: uuid.UUID, data: SessionUpdate) -> SessionOut:
    session = _locked_session(db, institution_id, session_id)
    if session.status == SessionStatus.cancelled:
        raise conflict("session_cancelled", "A cancelled session cannot be changed; schedule a new one")
    changes = data.changes()
    _validate_times(changes.get("start_at", session.start_at), changes.get("end_at", session.end_at))
    if "faculty_assignment_id" in changes:
        assignment = _usable_assignment(db, institution_id, changes.pop("faculty_assignment_id"))
        session.faculty_assignment_id = assignment.id
        session.faculty_membership_id = assignment.faculty_membership_id
        session.course_id = assignment.course_id
        session.subject_id = assignment.subject_id
    if changes.get("room_id") is not None and changes["room_id"] != session.room_id:
        _usable_room(db, institution_id, changes["room_id"])
    for name, value in changes.items():
        setattr(session, name, value)
    _flush(db)
    db.commit()
    return _reload_session(db, institution_id, session.id)


def cancel_session(db: Session, institution_id: uuid.UUID, session_id: uuid.UUID) -> SessionOut:
    session = _locked_session(db, institution_id, session_id)
    if session.status != SessionStatus.cancelled:
        session.status = SessionStatus.cancelled
        db.flush()
        db.commit()
    return _reload_session(db, institution_id, session.id)


# ---- Weekly timetable ------------------------------------------------------


@dataclass
class TimetableFilters:
    course_id: uuid.UUID | None = None
    subject_id: uuid.UUID | None = None
    room_id: uuid.UUID | None = None
    faculty_membership_id: uuid.UUID | None = None
    include_cancelled: bool = True


def week_window(zone: ZoneInfo, week_of: date | None) -> tuple[date, datetime, datetime]:
    """Monday 00:00 to the next Monday 00:00 in the institution's timezone.
    Built from local wall-clock dates, so a DST change inside the week yields
    a 167- or 169-hour window rather than shifted boundaries."""
    day = week_of or datetime.now(zone).date()
    monday = day - timedelta(days=day.weekday())
    start = datetime.combine(monday, time.min, tzinfo=zone)
    end = datetime.combine(monday + timedelta(days=7), time.min, tzinfo=zone)
    return monday, start, end


def _week(db: Session, tenant: TenantContext, week_of: date | None, condition, filters: TimetableFilters) -> TimetableWeek:
    zone = institution_zone(tenant.institution)
    monday, start, end = week_window(zone, week_of)
    query = _session_base(tenant.institution_id).where(ClassSession.start_at < end, ClassSession.end_at > start)
    if condition is not None:
        query = query.where(condition)
    for column, value in (
        (ClassSession.course_id, filters.course_id),
        (ClassSession.subject_id, filters.subject_id),
        (ClassSession.room_id, filters.room_id),
        (ClassSession.faculty_membership_id, filters.faculty_membership_id),
    ):
        if value is not None:
            query = query.where(column == value)
    if not filters.include_cancelled:
        query = query.where(ClassSession.status == SessionStatus.scheduled)
    rows = db.execute(query.order_by(ClassSession.start_at, Course.code, Subject.code, ClassSession.id))
    return TimetableWeek(
        timezone=zone.key,
        week_start=monday,
        week_end=monday + timedelta(days=7),
        starts_at=start,
        ends_at=end,
        sessions=[_session_out(row) for row in rows],
    )


def institution_week(db: Session, tenant: TenantContext, week_of: date | None, filters: TimetableFilters) -> TimetableWeek:
    return _week(db, tenant, week_of, None, filters)


def my_week(db: Session, tenant: TenantContext, week_of: date | None, include_cancelled: bool) -> TimetableWeek:
    return _week(
        db, tenant, week_of, _personal_condition(tenant.membership.id), TimetableFilters(include_cancelled=include_cancelled)
    )
