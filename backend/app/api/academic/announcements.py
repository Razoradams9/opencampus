"""Academic announcements (M4.6). Rules: services/academic/announcements.py."""

import uuid

from fastapi import APIRouter, status

from app.api.deps import CurrentTenant, DbSession, Pagination
from app.models import PublicationStatus
from app.schemas.academic import AnnouncementCreate, AnnouncementOut, AnnouncementUpdate
from app.services.academic import announcements as service

router = APIRouter()


@router.get("/announcements", response_model=list[AnnouncementOut])
def feed(tenant: CurrentTenant, db: DbSession, page: Pagination, include_expired: bool = False):
    """Published announcements intended for the caller, newest first."""
    return service.feed(db, tenant, include_expired, limit=page.limit, offset=page.offset)


@router.post("/announcements", status_code=status.HTTP_201_CREATED, response_model=AnnouncementOut)
def create(body: AnnouncementCreate, tenant: CurrentTenant, db: DbSession):
    return service.create(db, tenant, body)


@router.get("/announcements/managed", response_model=list[AnnouncementOut])
def managed(tenant: CurrentTenant, db: DbSession, page: Pagination, status: PublicationStatus | None = None):
    return service.managed(db, tenant, status, limit=page.limit, offset=page.offset)


@router.get("/announcements/{announcement_id}", response_model=AnnouncementOut)
def get(announcement_id: uuid.UUID, tenant: CurrentTenant, db: DbSession):
    return service.get(db, tenant, announcement_id)


@router.patch("/announcements/{announcement_id}", response_model=AnnouncementOut)
def update(announcement_id: uuid.UUID, body: AnnouncementUpdate, tenant: CurrentTenant, db: DbSession):
    return service.update(db, tenant, announcement_id, body)


@router.post("/announcements/{announcement_id}/publish", response_model=AnnouncementOut)
def publish(announcement_id: uuid.UUID, tenant: CurrentTenant, db: DbSession):
    return service.set_status(db, tenant, announcement_id, PublicationStatus.published)


@router.post("/announcements/{announcement_id}/archive", response_model=AnnouncementOut)
def archive(announcement_id: uuid.UUID, tenant: CurrentTenant, db: DbSession):
    return service.set_status(db, tenant, announcement_id, PublicationStatus.archived)
