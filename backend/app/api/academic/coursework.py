"""Assignments and submissions (M4.5). Rules: services/academic/coursework.py."""

import uuid

from fastapi import APIRouter, status

from app.api.deps import CurrentTenant, DbSession, Pagination
from app.models import PublicationStatus
from app.schemas.academic import (
    AssignmentWorkCreate,
    AssignmentWorkOut,
    AssignmentWorkUpdate,
    GradeCreate,
    SubmissionCreate,
    SubmissionOut,
)
from app.services.academic import coursework as service

router = APIRouter()


@router.get("/subjects/{subject_id}/assignments", response_model=list[AssignmentWorkOut])
def subject_assignments(subject_id: uuid.UUID, tenant: CurrentTenant, db: DbSession):
    return service.list_for_subject(db, tenant, subject_id)


@router.post("/subjects/{subject_id}/assignments", status_code=status.HTTP_201_CREATED, response_model=AssignmentWorkOut)
def create_assignment(subject_id: uuid.UUID, body: AssignmentWorkCreate, tenant: CurrentTenant, db: DbSession):
    return service.create(db, tenant, subject_id, body)


@router.get("/assignments/me", response_model=list[AssignmentWorkOut])
def my_assignments(tenant: CurrentTenant, db: DbSession):
    """Assignments for the caller's active enrolments, with their own status."""
    return service.list_mine(db, tenant)


@router.get("/assignments/managed", response_model=list[AssignmentWorkOut])
def managed_assignments(
    tenant: CurrentTenant, db: DbSession, page: Pagination, subject_id: uuid.UUID | None = None, status: PublicationStatus | None = None
):
    return service.list_managed(db, tenant, subject_id, status, limit=page.limit, offset=page.offset)


@router.get("/assignments/{assignment_id}", response_model=AssignmentWorkOut)
def get_assignment(assignment_id: uuid.UUID, tenant: CurrentTenant, db: DbSession):
    return service.get(db, tenant, assignment_id)


@router.patch("/assignments/{assignment_id}", response_model=AssignmentWorkOut)
def update_assignment(assignment_id: uuid.UUID, body: AssignmentWorkUpdate, tenant: CurrentTenant, db: DbSession):
    return service.update(db, tenant, assignment_id, body)


@router.post("/assignments/{assignment_id}/publish", response_model=AssignmentWorkOut)
def publish_assignment(assignment_id: uuid.UUID, tenant: CurrentTenant, db: DbSession):
    return service.set_status(db, tenant, assignment_id, PublicationStatus.published)


@router.post("/assignments/{assignment_id}/archive", response_model=AssignmentWorkOut)
def archive_assignment(assignment_id: uuid.UUID, tenant: CurrentTenant, db: DbSession):
    return service.set_status(db, tenant, assignment_id, PublicationStatus.archived)


@router.post("/assignments/{assignment_id}/submissions", status_code=status.HTTP_201_CREATED, response_model=SubmissionOut)
def submit(assignment_id: uuid.UUID, body: SubmissionCreate, tenant: CurrentTenant, db: DbSession):
    return service.submit(db, tenant, assignment_id, body)


@router.get("/assignments/{assignment_id}/submissions/me", response_model=list[SubmissionOut])
def my_submissions(assignment_id: uuid.UUID, tenant: CurrentTenant, db: DbSession):
    """The caller's submission history for the assignment, oldest first."""
    return service.my_submissions(db, tenant, assignment_id)


@router.get("/assignments/{assignment_id}/submissions", response_model=list[SubmissionOut])
def assignment_submissions(assignment_id: uuid.UUID, tenant: CurrentTenant, db: DbSession, latest_only: bool = False):
    """All submissions (managers only). latest_only keeps each student's newest attempt."""
    return service.assignment_submissions(db, tenant, assignment_id, latest_only)


@router.get("/submissions/{submission_id}", response_model=SubmissionOut)
def get_submission(submission_id: uuid.UUID, tenant: CurrentTenant, db: DbSession):
    return service.get_submission(db, tenant, submission_id)


@router.post("/submissions/{submission_id}/grades", status_code=status.HTTP_201_CREATED, response_model=SubmissionOut)
def grade_submission(submission_id: uuid.UUID, body: GradeCreate, tenant: CurrentTenant, db: DbSession):
    """Add a grade. Regrading adds another row; history is kept."""
    return service.grade(db, tenant, submission_id, body)
