"""Learning resources and notes (M4.4). Rules: services/academic/resources.py."""

import uuid

from fastapi import APIRouter, status

from app.api.deps import CurrentTenant, DbSession, Pagination
from app.models import PublicationStatus
from app.schemas.academic import ResourceCreate, ResourceOut, ResourceUpdate
from app.services.academic import resources as service

router = APIRouter()


@router.get("/subjects/{subject_id}/resources", response_model=list[ResourceOut])
def subject_resources(subject_id: uuid.UUID, tenant: CurrentTenant, db: DbSession, status: PublicationStatus | None = None):
    return service.list_for_subject(db, tenant, subject_id, status)


@router.post("/subjects/{subject_id}/resources", status_code=status.HTTP_201_CREATED, response_model=ResourceOut)
def create_resource(subject_id: uuid.UUID, body: ResourceCreate, tenant: CurrentTenant, db: DbSession):
    return service.create(db, tenant, subject_id, body)


@router.get("/resources/me", response_model=list[ResourceOut])
def my_resources(tenant: CurrentTenant, db: DbSession, subject_id: uuid.UUID | None = None):
    """Published resources for the caller's active enrolments."""
    return service.list_available(db, tenant, subject_id)


@router.get("/resources/managed", response_model=list[ResourceOut])
def managed_resources(
    tenant: CurrentTenant, db: DbSession, page: Pagination, subject_id: uuid.UUID | None = None, status: PublicationStatus | None = None
):
    """Faculty: resources of subjects they teach. Admins: all."""
    return service.list_managed(db, tenant, subject_id, status, limit=page.limit, offset=page.offset)


@router.get("/resources/{resource_id}", response_model=ResourceOut)
def get_resource(resource_id: uuid.UUID, tenant: CurrentTenant, db: DbSession):
    return service.get(db, tenant, resource_id)


@router.patch("/resources/{resource_id}", response_model=ResourceOut)
def update_resource(resource_id: uuid.UUID, body: ResourceUpdate, tenant: CurrentTenant, db: DbSession):
    return service.update(db, tenant, resource_id, body)


@router.post("/resources/{resource_id}/publish", response_model=ResourceOut)
def publish_resource(resource_id: uuid.UUID, tenant: CurrentTenant, db: DbSession):
    return service.set_status(db, tenant, resource_id, PublicationStatus.published)


@router.post("/resources/{resource_id}/archive", response_model=ResourceOut)
def archive_resource(resource_id: uuid.UUID, tenant: CurrentTenant, db: DbSession):
    return service.set_status(db, tenant, resource_id, PublicationStatus.archived)
