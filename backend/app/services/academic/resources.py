"""Learning resources and notes (M4.4).

Visibility:
  college_admin  every resource in the institution
  faculty        every resource (any status) of subjects they teach
  student        PUBLISHED resources of subjects in courses they are actively
                 enrolled in
Writes: admins, or faculty teaching the subject.
"""

import uuid

from sqlalchemy import Select, and_, select
from sqlalchemy.orm import Session, aliased

from app.api.deps import TenantContext
from app.core.errors import ApiError, forbidden
from app.core.security import utcnow
from app.models import (
    AcademicStatus,
    Course,
    LearningResource,
    Membership,
    MembershipRole,
    PublicationStatus,
    ResourceType,
    Subject,
    User,
)
from app.schemas.academic import (
    CourseRef,
    ResourceCreate,
    ResourceOut,
    ResourceUpdate,
    SubjectRef,
    TeacherRef,
    check_resource_content,
)
from app.services.academic import access
from app.services.academic.common import conflict, not_found
from app.services.storage import get_file_storage

Author = aliased(Membership, name="author")


def _base(institution_id: uuid.UUID) -> Select:
    return (
        select(LearningResource, Course, Subject, Author.id, User.full_name)
        .join(Course, and_(Course.institution_id == LearningResource.institution_id, Course.id == LearningResource.course_id))
        .join(Subject, and_(Subject.institution_id == LearningResource.institution_id, Subject.id == LearningResource.subject_id))
        .join(Author, and_(Author.institution_id == LearningResource.institution_id, Author.id == LearningResource.created_by_membership_id))
        .join(User, User.id == Author.user_id)
        .where(LearningResource.institution_id == institution_id)
    )


def _visible(query: Select, tenant: TenantContext) -> Select:
    if access.is_admin(tenant):
        return query
    me = tenant.membership.id
    if tenant.role == MembershipRole.faculty:
        return query.where(access.teaches_subject(me, LearningResource.institution_id, LearningResource.subject_id))
    return query.where(
        LearningResource.status == PublicationStatus.published,
        access.enrolled_in_course(me, LearningResource.institution_id, LearningResource.course_id),
    )


def _out(row) -> ResourceOut:
    resource, course, subject, author_id, author_name = row
    return ResourceOut(
        id=resource.id,
        course=CourseRef(id=course.id, name=course.name, code=course.code, status=course.status),
        subject=SubjectRef(id=subject.id, name=subject.name, code=subject.code, semester=subject.semester, credits=float(subject.credits)),
        title=resource.title,
        description=resource.description,
        resource_type=resource.resource_type,
        topic=resource.topic,
        body=resource.body,
        external_url=resource.external_url,
        file_available=bool(resource.storage_key) and get_file_storage() is not None,
        status=resource.status,
        created_by=TeacherRef(membership_id=author_id, full_name=author_name),
        published_at=resource.published_at,
        created_at=resource.created_at,
        updated_at=resource.updated_at,
    )


def _order(query: Select) -> Select:
    return query.order_by(Subject.code, LearningResource.topic.nulls_last(), LearningResource.created_at, LearningResource.id)


def list_for_subject(db: Session, tenant: TenantContext, subject_id: uuid.UUID, status: PublicationStatus | None) -> list[ResourceOut]:
    subject, course = access.subject_with_course(db, tenant.institution_id, subject_id)
    if not (access.can_manage_subject(db, tenant, subject.id) or access.can_study_course(db, tenant, course.id)):
        raise forbidden("not_enrolled_or_assigned", "You are not enrolled in or teaching this subject")
    query = _visible(_base(tenant.institution_id), tenant).where(LearningResource.subject_id == subject.id)
    if status is not None:
        query = query.where(LearningResource.status == status)
    return [_out(r) for r in db.execute(_order(query))]


def list_available(db: Session, tenant: TenantContext, subject_id: uuid.UUID | None) -> list[ResourceOut]:
    """Published resources for the caller's active enrolments (student view)."""
    query = _base(tenant.institution_id).where(
        LearningResource.status == PublicationStatus.published,
        access.enrolled_in_course(tenant.membership.id, LearningResource.institution_id, LearningResource.course_id),
    )
    if subject_id is not None:
        query = query.where(LearningResource.subject_id == subject_id)
    return [_out(r) for r in db.execute(_order(query))]


def list_managed(
    db: Session, tenant: TenantContext, subject_id: uuid.UUID | None, status: PublicationStatus | None, *, limit: int, offset: int
) -> list[ResourceOut]:
    """Faculty: resources of subjects they teach. Admins: all."""
    if not (access.is_admin(tenant) or tenant.role == MembershipRole.faculty):
        raise forbidden("insufficient_role", "Only faculty and administrators manage resources")
    query = _visible(_base(tenant.institution_id), tenant)
    if subject_id is not None:
        query = query.where(LearningResource.subject_id == subject_id)
    if status is not None:
        query = query.where(LearningResource.status == status)
    return [_out(r) for r in db.execute(_order(query).limit(limit).offset(offset))]


def get(db: Session, tenant: TenantContext, resource_id: uuid.UUID) -> ResourceOut:
    row = db.execute(_visible(_base(tenant.institution_id), tenant).where(LearningResource.id == resource_id)).one_or_none()
    if row is None:
        raise not_found("resource", "Resource")
    return _out(row)


def _reload(db: Session, institution_id: uuid.UUID, resource_id: uuid.UUID) -> ResourceOut:
    return _out(db.execute(_base(institution_id).where(LearningResource.id == resource_id)).one())


def create(db: Session, tenant: TenantContext, subject_id: uuid.UUID, data: ResourceCreate) -> ResourceOut:
    subject, course = access.subject_with_course(db, tenant.institution_id, subject_id)
    access.require_manage_subject(db, tenant, subject.id)
    if subject.status != AcademicStatus.active or course.status != AcademicStatus.active:
        raise conflict("subject_archived", "The subject or its course is archived")
    resource = LearningResource(
        institution_id=tenant.institution_id,
        course_id=course.id,
        subject_id=subject.id,
        created_by_membership_id=tenant.membership.id,
        **data.model_dump(),
    )
    db.add(resource)
    db.flush()
    db.commit()
    return _reload(db, tenant.institution_id, resource.id)


def _manageable(db: Session, tenant: TenantContext, resource_id: uuid.UUID) -> LearningResource:
    resource = db.scalar(
        select(LearningResource)
        .where(LearningResource.institution_id == tenant.institution_id, LearningResource.id == resource_id)
        .with_for_update()
    )
    # Students and non-teaching faculty get 404: they may not even see drafts.
    if resource is None or not access.can_manage_subject(db, tenant, resource.subject_id):
        if resource is not None and tenant.role == MembershipRole.faculty:
            raise forbidden("not_assigned", "You are not assigned to teach this subject")
        if resource is not None and tenant.role == MembershipRole.student:
            raise forbidden("insufficient_role", "Students cannot change resources")
        raise not_found("resource", "Resource")
    return resource


def update(db: Session, tenant: TenantContext, resource_id: uuid.UUID, data: ResourceUpdate) -> ResourceOut:
    resource = _manageable(db, tenant, resource_id)
    if resource.status == PublicationStatus.archived:
        raise conflict("resource_archived", "Archived resources are read-only")
    changes = data.changes()
    merged = {k: changes.get(k, getattr(resource, k)) for k in ("resource_type", "body", "external_url")}
    try:
        check_resource_content(ResourceType(merged["resource_type"]), merged["body"], merged["external_url"])
    except ValueError as exc:
        raise ApiError(422, "invalid_resource_content", str(exc)) from None
    for name, value in changes.items():
        setattr(resource, name, value)
    db.flush()
    db.commit()
    return _reload(db, tenant.institution_id, resource.id)


def set_status(db: Session, tenant: TenantContext, resource_id: uuid.UUID, status: PublicationStatus) -> ResourceOut:
    resource = _manageable(db, tenant, resource_id)
    if status == PublicationStatus.published:
        if resource.status == PublicationStatus.archived:
            raise conflict("resource_archived", "Archived resources cannot be republished")
        resource.published_at = resource.published_at or utcnow()
    resource.status = status
    db.flush()
    db.commit()
    return _reload(db, tenant.institution_id, resource.id)
