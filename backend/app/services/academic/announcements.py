"""Academic announcements (M4.6).

Feed visibility (every read endpoint applies it in SQL):
  published, published_at <= now, not expired (unless explicitly requested), and
    institution        -> every member
    course             -> student actively enrolled in the course, or faculty
                          with an active assignment in it
    subject            -> student enrolled in the subject's course, or faculty
                          teaching the subject
    subject_students   -> student enrolled in the subject's course
  College admins see every published announcement.
Authoring:
  college_admin  any audience in the institution
  faculty        subject / subject_students audiences for subjects they teach
The audience is validated server-side on create AND on every update, so it
cannot be widened by editing request parameters.
"""

import uuid
from datetime import datetime

from sqlalchemy import Select, and_, false, or_, select, true
from sqlalchemy.orm import Session, aliased

from app.api.deps import TenantContext
from app.core.errors import ApiError, forbidden
from app.core.security import utcnow
from app.models import (
    AcademicStatus,
    Announcement,
    AnnouncementAudience,
    Course,
    Membership,
    MembershipRole,
    PublicationStatus,
    Subject,
    User,
)
from app.schemas.academic import (
    AnnouncementCreate,
    AnnouncementOut,
    AnnouncementUpdate,
    CourseRef,
    SubjectRef,
    TeacherRef,
    check_audience,
)
from app.services.academic import access
from app.services.academic.common import conflict, not_found

Author = aliased(Membership, name="author")
SUBJECT_AUDIENCES = (AnnouncementAudience.subject, AnnouncementAudience.subject_students)


def _base(institution_id: uuid.UUID) -> Select:
    return (
        select(Announcement, Course, Subject, Author.id, User.full_name)
        .outerjoin(Course, and_(Course.institution_id == Announcement.institution_id, Course.id == Announcement.course_id))
        .outerjoin(Subject, and_(Subject.institution_id == Announcement.institution_id, Subject.id == Announcement.subject_id))
        .join(Author, and_(Author.institution_id == Announcement.institution_id, Author.id == Announcement.created_by_membership_id))
        .join(User, User.id == Author.user_id)
        .where(Announcement.institution_id == institution_id)
    )


def _audience_condition(tenant: TenantContext):
    """Which published announcements are *intended for* the caller."""
    if access.is_admin(tenant):
        return true()
    me = tenant.membership.id
    inst = Announcement.institution_id
    if tenant.role == MembershipRole.student:
        enrolled = access.enrolled_in_course(me, inst, Announcement.course_id)
        return or_(
            Announcement.audience == AnnouncementAudience.institution,
            and_(Announcement.audience.in_((AnnouncementAudience.course, *SUBJECT_AUDIENCES)), enrolled),
        )
    if tenant.role == MembershipRole.faculty:
        return or_(
            Announcement.audience == AnnouncementAudience.institution,
            and_(Announcement.audience == AnnouncementAudience.course, access.teaches_in_course(me, inst, Announcement.course_id)),
            and_(Announcement.audience == AnnouncementAudience.subject, access.teaches_subject(me, inst, Announcement.subject_id)),
        )
    return false()


def _live(now: datetime, include_expired: bool):
    conditions = [Announcement.status == PublicationStatus.published, Announcement.published_at <= now]
    if not include_expired:
        conditions.append(or_(Announcement.expires_at.is_(None), Announcement.expires_at > now))
    return and_(*conditions)


def _manage_condition(tenant: TenantContext):
    if access.is_admin(tenant):
        return true()
    if tenant.role == MembershipRole.faculty:
        return and_(
            Announcement.audience.in_(SUBJECT_AUDIENCES),
            access.teaches_subject(tenant.membership.id, Announcement.institution_id, Announcement.subject_id),
        )
    return false()


def _out(row, now: datetime) -> AnnouncementOut:
    a, course, subject, author_id, author_name = row
    return AnnouncementOut(
        id=a.id,
        title=a.title,
        body=a.body,
        priority=a.priority,
        audience=a.audience,
        course=CourseRef(id=course.id, name=course.name, code=course.code, status=course.status) if course else None,
        subject=SubjectRef(id=subject.id, name=subject.name, code=subject.code, semester=subject.semester, credits=float(subject.credits)) if subject else None,
        status=a.status,
        published_at=a.published_at,
        expires_at=a.expires_at,
        expired=a.expires_at is not None and a.expires_at <= now,
        created_by=TeacherRef(membership_id=author_id, full_name=author_name),
        created_at=a.created_at,
        updated_at=a.updated_at,
    )


def feed(db: Session, tenant: TenantContext, include_expired: bool, *, limit: int, offset: int) -> list[AnnouncementOut]:
    now = utcnow()
    query = _base(tenant.institution_id).where(_live(now, include_expired), _audience_condition(tenant))
    query = query.order_by(Announcement.published_at.desc(), Announcement.id).limit(limit).offset(offset)
    return [_out(r, now) for r in db.execute(query)]


def managed(db: Session, tenant: TenantContext, status: PublicationStatus | None, *, limit: int, offset: int) -> list[AnnouncementOut]:
    if not (access.is_admin(tenant) or tenant.role == MembershipRole.faculty):
        raise forbidden("insufficient_role", "Only faculty and administrators manage announcements")
    now = utcnow()
    query = _base(tenant.institution_id).where(_manage_condition(tenant))
    if status is not None:
        query = query.where(Announcement.status == status)
    query = query.order_by(Announcement.updated_at.desc(), Announcement.id).limit(limit).offset(offset)
    return [_out(r, now) for r in db.execute(query)]


def get(db: Session, tenant: TenantContext, announcement_id: uuid.UUID) -> AnnouncementOut:
    now = utcnow()
    readable = or_(and_(_live(now, include_expired=True), _audience_condition(tenant)), _manage_condition(tenant))
    row = db.execute(_base(tenant.institution_id).where(Announcement.id == announcement_id, readable)).one_or_none()
    if row is None:
        raise not_found("announcement", "Announcement")
    return _out(row, now)


def _resolve_target(
    db: Session, tenant: TenantContext, audience: AnnouncementAudience, course_id: uuid.UUID | None, subject_id: uuid.UUID | None
) -> tuple[uuid.UUID | None, uuid.UUID | None]:
    """Check the caller may address this audience; return (course_id, subject_id)."""
    admin = access.is_admin(tenant)
    if audience == AnnouncementAudience.institution:
        if not admin:
            raise forbidden("audience_not_permitted", "Only administrators can address the whole institution")
        return None, None
    if audience == AnnouncementAudience.course:
        if not admin:
            raise forbidden("audience_not_permitted", "Faculty can address only subjects they teach")
        course = db.scalar(select(Course).where(Course.institution_id == tenant.institution_id, Course.id == course_id))
        if course is None:
            raise not_found("course", "Course")
        if course.status != AcademicStatus.active:
            raise conflict("course_archived", "The course is archived")
        return course.id, None
    subject, course = access.subject_with_course(db, tenant.institution_id, subject_id)
    if not access.can_manage_subject(db, tenant, subject.id):
        raise forbidden("audience_not_permitted", "You can only address subjects you teach")
    if subject.status != AcademicStatus.active or course.status != AcademicStatus.active:
        raise conflict("subject_archived", "The subject or its course is archived")
    return course.id, subject.id


def _reload(db: Session, tenant: TenantContext, announcement_id: uuid.UUID) -> AnnouncementOut:
    return _out(db.execute(_base(tenant.institution_id).where(Announcement.id == announcement_id)).one(), utcnow())


def create(db: Session, tenant: TenantContext, data: AnnouncementCreate) -> AnnouncementOut:
    if not (access.is_admin(tenant) or tenant.role == MembershipRole.faculty):
        raise forbidden("insufficient_role", "Only faculty and administrators publish announcements")
    course_id, subject_id = _resolve_target(db, tenant, data.audience, data.course_id, data.subject_id)
    announcement = Announcement(
        institution_id=tenant.institution_id,
        created_by_membership_id=tenant.membership.id,
        title=data.title,
        body=data.body,
        priority=data.priority,
        audience=data.audience,
        course_id=course_id,
        subject_id=subject_id,
        expires_at=data.expires_at,
    )
    db.add(announcement)
    db.flush()
    db.commit()
    return _reload(db, tenant, announcement.id)


def _manageable(db: Session, tenant: TenantContext, announcement_id: uuid.UUID) -> Announcement:
    if not (access.is_admin(tenant) or tenant.role == MembershipRole.faculty):
        raise forbidden("insufficient_role", "Only faculty and administrators manage announcements")
    announcement = db.scalar(
        select(Announcement)
        .where(Announcement.institution_id == tenant.institution_id, Announcement.id == announcement_id, _manage_condition(tenant))
        .with_for_update()
    )
    if announcement is None:
        raise not_found("announcement", "Announcement")
    return announcement


def update(db: Session, tenant: TenantContext, announcement_id: uuid.UUID, data: AnnouncementUpdate) -> AnnouncementOut:
    announcement = _manageable(db, tenant, announcement_id)
    if announcement.status != PublicationStatus.draft:
        raise conflict("announcement_not_draft", "Only drafts can be edited")
    changes = data.changes()
    if {"audience", "course_id", "subject_id"} & changes.keys():
        # Changing the target means restating it in full (audience plus its
        # id); omitted ids are treated as absent, never inherited.
        audience = changes.get("audience", announcement.audience)
        course_id = changes.get("course_id")
        subject_id = changes.get("subject_id")
        try:
            check_audience(AnnouncementAudience(audience), course_id, subject_id)
        except ValueError as exc:
            raise ApiError(422, "invalid_audience", str(exc)) from None
        announcement.audience = audience
        announcement.course_id, announcement.subject_id = _resolve_target(db, tenant, AnnouncementAudience(audience), course_id, subject_id)
    for name in ("title", "body", "priority", "expires_at"):
        if name in changes:
            setattr(announcement, name, changes[name])
    db.flush()
    db.commit()
    return _reload(db, tenant, announcement.id)


def set_status(db: Session, tenant: TenantContext, announcement_id: uuid.UUID, status: PublicationStatus) -> AnnouncementOut:
    announcement = _manageable(db, tenant, announcement_id)
    if status == PublicationStatus.published:
        if announcement.status == PublicationStatus.archived:
            raise conflict("announcement_archived", "Archived announcements cannot be republished")
        if announcement.status == PublicationStatus.draft:
            now = utcnow()
            if announcement.expires_at is not None and announcement.expires_at <= now:
                raise ApiError(422, "already_expired", "The expiry time has already passed")
            # Publishing re-checks the audience: the author may have lost the grant.
            _resolve_target(db, tenant, announcement.audience, announcement.course_id, announcement.subject_id)
            announcement.published_at = now
    announcement.status = status
    db.flush()
    db.commit()
    return _reload(db, tenant, announcement.id)
