"""Courses and subjects (M4.1).

Read: every active member (student, faculty, college admin). Non-admins see
active records only; archived ones answer 404 for them.
Write and archive/restore: college admins only.
"""

import uuid

from fastapi import APIRouter, status

from app.api.deps import CollegeAdmin, CurrentTenant, DbSession, Pagination
from app.models import AcademicStatus, MembershipRole
from app.schemas.academic import CourseCreate, CourseOut, CourseUpdate, SubjectCreate, SubjectOut, SubjectUpdate
from app.services.academic import courses as service

router = APIRouter()


def _visible_status(tenant, requested: AcademicStatus | None) -> AcademicStatus | None:
    """Admins may filter by any status (default: all); others only see active."""
    return requested if tenant.role == MembershipRole.college_admin else AcademicStatus.active


@router.get("/courses", response_model=list[CourseOut])
def list_courses(tenant: CurrentTenant, db: DbSession, page: Pagination, status: AcademicStatus | None = None):
    return service.list_courses(
        db, tenant.institution_id, status=_visible_status(tenant, status), limit=page.limit, offset=page.offset
    )


@router.post("/courses", status_code=status.HTTP_201_CREATED, response_model=CourseOut)
def create_course(body: CourseCreate, tenant: CollegeAdmin, db: DbSession):
    return service.create_course(db, tenant.institution_id, body)


@router.get("/courses/{course_id}", response_model=CourseOut)
def get_course(course_id: uuid.UUID, tenant: CurrentTenant, db: DbSession):
    return service.get_course(db, tenant.institution_id, course_id, active_only=tenant.role != MembershipRole.college_admin)


@router.patch("/courses/{course_id}", response_model=CourseOut)
def update_course(course_id: uuid.UUID, body: CourseUpdate, tenant: CollegeAdmin, db: DbSession):
    return service.update_course(db, tenant.institution_id, course_id, body)


@router.post("/courses/{course_id}/archive", response_model=CourseOut)
def archive_course(course_id: uuid.UUID, tenant: CollegeAdmin, db: DbSession):
    return service.set_course_status(db, tenant.institution_id, course_id, AcademicStatus.archived)


@router.post("/courses/{course_id}/restore", response_model=CourseOut)
def restore_course(course_id: uuid.UUID, tenant: CollegeAdmin, db: DbSession):
    return service.set_course_status(db, tenant.institution_id, course_id, AcademicStatus.active)


@router.get("/courses/{course_id}/subjects", response_model=list[SubjectOut])
def list_subjects(course_id: uuid.UUID, tenant: CurrentTenant, db: DbSession, status: AcademicStatus | None = None):
    admin = tenant.role == MembershipRole.college_admin
    return service.list_subjects(
        db, tenant.institution_id, course_id, status=_visible_status(tenant, status), active_course_only=not admin
    )


@router.post("/courses/{course_id}/subjects", status_code=status.HTTP_201_CREATED, response_model=SubjectOut)
def create_subject(course_id: uuid.UUID, body: SubjectCreate, tenant: CollegeAdmin, db: DbSession):
    return service.create_subject(db, tenant.institution_id, course_id, body)


@router.get("/subjects/{subject_id}", response_model=SubjectOut)
def get_subject(subject_id: uuid.UUID, tenant: CurrentTenant, db: DbSession):
    return service.get_subject(
        db, tenant.institution_id, subject_id, active_only=tenant.role != MembershipRole.college_admin
    )


@router.patch("/subjects/{subject_id}", response_model=SubjectOut)
def update_subject(subject_id: uuid.UUID, body: SubjectUpdate, tenant: CollegeAdmin, db: DbSession):
    return service.update_subject(db, tenant.institution_id, subject_id, body)


@router.post("/subjects/{subject_id}/archive", response_model=SubjectOut)
def archive_subject(subject_id: uuid.UUID, tenant: CollegeAdmin, db: DbSession):
    return service.set_subject_status(db, tenant.institution_id, subject_id, AcademicStatus.archived)


@router.post("/subjects/{subject_id}/restore", response_model=SubjectOut)
def restore_subject(subject_id: uuid.UUID, tenant: CollegeAdmin, db: DbSession):
    return service.set_subject_status(db, tenant.institution_id, subject_id, AcademicStatus.active)
