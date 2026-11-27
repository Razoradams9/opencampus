"""Rooms, faculty assignments, sessions and timetables (M4.3).

Scheduling (rooms, assignments, sessions) is managed by college admins only.
Faculty and students read their own timetable; faculty also read their own
assignments. The institution-wide timetable is admin-only.
"""

import uuid
from datetime import date

from fastapi import APIRouter, status

from app.api.deps import CollegeAdmin, CurrentTenant, DbSession, Pagination
from app.models import AcademicStatus, AssignmentStatus, MembershipRole
from app.schemas.academic import (
    AssignmentCreate,
    AssignmentOut,
    RoomCreate,
    RoomOut,
    RoomUpdate,
    SessionCreate,
    SessionOut,
    SessionUpdate,
    TimetableWeek,
)
from app.services.academic import timetable as service

router = APIRouter()


# ---- Rooms -----------------------------------------------------------------


@router.get("/rooms", response_model=list[RoomOut])
def list_rooms(tenant: CurrentTenant, db: DbSession, status: AcademicStatus | None = None):
    visible = status if tenant.role == MembershipRole.college_admin else AcademicStatus.active
    return service.list_rooms(db, tenant.institution_id, visible)


@router.post("/rooms", status_code=status.HTTP_201_CREATED, response_model=RoomOut)
def create_room(body: RoomCreate, tenant: CollegeAdmin, db: DbSession):
    return service.create_room(db, tenant.institution_id, body)


@router.get("/rooms/{room_id}", response_model=RoomOut)
def get_room(room_id: uuid.UUID, tenant: CurrentTenant, db: DbSession):
    return service.get_room(db, tenant.institution_id, room_id, active_only=tenant.role != MembershipRole.college_admin)


@router.patch("/rooms/{room_id}", response_model=RoomOut)
def update_room(room_id: uuid.UUID, body: RoomUpdate, tenant: CollegeAdmin, db: DbSession):
    return service.update_room(db, tenant.institution_id, room_id, body)


@router.post("/rooms/{room_id}/archive", response_model=RoomOut)
def archive_room(room_id: uuid.UUID, tenant: CollegeAdmin, db: DbSession):
    return service.set_room_status(db, tenant.institution_id, room_id, AcademicStatus.archived)


@router.post("/rooms/{room_id}/restore", response_model=RoomOut)
def restore_room(room_id: uuid.UUID, tenant: CollegeAdmin, db: DbSession):
    return service.set_room_status(db, tenant.institution_id, room_id, AcademicStatus.active)


# ---- Faculty assignments ---------------------------------------------------


@router.get("/faculty-assignments", response_model=list[AssignmentOut])
def list_assignments(
    tenant: CurrentTenant,
    db: DbSession,
    page: Pagination,
    course_id: uuid.UUID | None = None,
    subject_id: uuid.UUID | None = None,
    faculty_membership_id: uuid.UUID | None = None,
    status: AssignmentStatus | None = None,
    academic_year: str | None = None,
):
    filters = service.AssignmentFilters(course_id, subject_id, faculty_membership_id, status, academic_year)
    return service.list_assignments(db, tenant, filters, limit=page.limit, offset=page.offset)


@router.post("/faculty-assignments", status_code=status.HTTP_201_CREATED, response_model=AssignmentOut)
def create_assignment(body: AssignmentCreate, tenant: CollegeAdmin, db: DbSession):
    return service.create_assignment(db, tenant.institution_id, body)


@router.get("/faculty-assignments/me", response_model=list[AssignmentOut])
def my_assignments(tenant: CurrentTenant, db: DbSession, status: AssignmentStatus | None = None):
    """Subjects the signed-in faculty member teaches."""
    return service.my_assignments(db, tenant, status)


@router.get("/faculty-assignments/{assignment_id}", response_model=AssignmentOut)
def get_assignment(assignment_id: uuid.UUID, tenant: CurrentTenant, db: DbSession):
    return service.get_assignment(db, tenant, assignment_id)


@router.post("/faculty-assignments/{assignment_id}/end", response_model=AssignmentOut)
def end_assignment(assignment_id: uuid.UUID, tenant: CollegeAdmin, db: DbSession):
    return service.end_assignment(db, tenant.institution_id, assignment_id)


# ---- Sessions and timetables -----------------------------------------------


@router.get("/timetable", response_model=TimetableWeek)
def institution_timetable(
    tenant: CollegeAdmin,
    db: DbSession,
    week: date | None = None,
    course_id: uuid.UUID | None = None,
    subject_id: uuid.UUID | None = None,
    room_id: uuid.UUID | None = None,
    faculty_membership_id: uuid.UUID | None = None,
    include_cancelled: bool = True,
):
    """The whole institution's week. `week` is any date in it (default: today
    in the institution's timezone)."""
    filters = service.TimetableFilters(course_id, subject_id, room_id, faculty_membership_id, include_cancelled)
    return service.institution_week(db, tenant, week, filters)


@router.get("/timetable/me", response_model=TimetableWeek)
def my_timetable(tenant: CurrentTenant, db: DbSession, week: date | None = None, include_cancelled: bool = True):
    """Sessions the caller teaches or attends (through an active enrolment)."""
    return service.my_week(db, tenant, week, include_cancelled)


@router.post("/timetable/sessions", status_code=status.HTTP_201_CREATED, response_model=SessionOut)
def create_session(body: SessionCreate, tenant: CollegeAdmin, db: DbSession):
    return service.create_session(db, tenant.institution_id, body)


@router.get("/timetable/sessions/{session_id}", response_model=SessionOut)
def get_session(session_id: uuid.UUID, tenant: CurrentTenant, db: DbSession):
    return service.get_session(db, tenant, session_id)


@router.patch("/timetable/sessions/{session_id}", response_model=SessionOut)
def update_session(session_id: uuid.UUID, body: SessionUpdate, tenant: CollegeAdmin, db: DbSession):
    return service.update_session(db, tenant.institution_id, session_id, body)


@router.post("/timetable/sessions/{session_id}/cancel", response_model=SessionOut)
def cancel_session(session_id: uuid.UUID, tenant: CollegeAdmin, db: DbSession):
    return service.cancel_session(db, tenant.institution_id, session_id)
