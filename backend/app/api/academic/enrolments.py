"""Student enrolments (M4.2).

Admins manage enrolments; students read their own; faculty read only what
an explicit teaching assignment grants. Students cannot enrol themselves.
"""

import uuid

from fastapi import APIRouter, status

from app.api.deps import CollegeAdmin, CurrentTenant, DbSession, Pagination
from app.models import EnrolmentStatus
from app.schemas.academic import EnrolmentCreate, EnrolmentOut, EnrolmentUpdate
from app.services.academic import enrolments as service

router = APIRouter()


@router.get("/enrolments", response_model=list[EnrolmentOut])
def list_enrolments(
    tenant: CurrentTenant,
    db: DbSession,
    page: Pagination,
    course_id: uuid.UUID | None = None,
    student_membership_id: uuid.UUID | None = None,
    status: EnrolmentStatus | None = None,
    academic_year: str | None = None,
):
    filters = service.EnrolmentFilters(course_id, student_membership_id, status, academic_year)
    return service.list_enrolments(db, tenant, filters, limit=page.limit, offset=page.offset)


@router.post("/enrolments", status_code=status.HTTP_201_CREATED, response_model=EnrolmentOut)
def create_enrolment(body: EnrolmentCreate, tenant: CollegeAdmin, db: DbSession):
    return service.create_enrolment(db, tenant.institution_id, body)


# Declared before /enrolments/{enrolment_id} so "me" is not parsed as an id.
@router.get("/enrolments/me", response_model=list[EnrolmentOut])
def my_enrolments(tenant: CurrentTenant, db: DbSession, status: EnrolmentStatus | None = None):
    """Courses the signed-in student is (or was) enrolled in."""
    return service.my_enrolments(db, tenant, status)


@router.get("/enrolments/{enrolment_id}", response_model=EnrolmentOut)
def get_enrolment(enrolment_id: uuid.UUID, tenant: CurrentTenant, db: DbSession):
    return service.get_enrolment(db, tenant, enrolment_id)


@router.patch("/enrolments/{enrolment_id}", response_model=EnrolmentOut)
def update_enrolment(enrolment_id: uuid.UUID, body: EnrolmentUpdate, tenant: CollegeAdmin, db: DbSession):
    return service.update_status(db, tenant.institution_id, enrolment_id, body.status)


@router.get("/courses/{course_id}/enrolments", response_model=list[EnrolmentOut])
def course_enrolments(
    course_id: uuid.UUID, tenant: CurrentTenant, db: DbSession, page: Pagination, status: EnrolmentStatus | None = None
):
    """Students enrolled in a course (roster)."""
    return service.list_course_enrolments(db, tenant, course_id, status, limit=page.limit, offset=page.offset)
