"""Student enrolments (M4.2).

Who sees what (enforced here, on top of tenant RLS):
  college_admin  every enrolment in the institution
  student        only enrolments of their own membership
  faculty        only enrolments matching one of their *active* teaching
                 assignments (same course, academic year and period)
"""

import uuid
from dataclasses import dataclass

from sqlalchemy import Select, exists, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import TenantContext
from app.core.errors import ApiError, forbidden
from app.core.security import utcnow
from app.models import (
    AcademicStatus,
    AssignmentStatus,
    Course,
    Enrolment,
    EnrolmentStatus,
    FacultyAssignment,
    Membership,
    MembershipRole,
    MembershipStatus,
    User,
)
from app.schemas.academic import CourseRef, EnrolmentCreate, EnrolmentOut, PersonRef
from app.services.academic.common import conflict, constraint_name, not_found

# Allowed status changes. withdrawn and completed are terminal.
TRANSITIONS: dict[EnrolmentStatus, frozenset[EnrolmentStatus]] = {
    EnrolmentStatus.active: frozenset({EnrolmentStatus.suspended, EnrolmentStatus.withdrawn, EnrolmentStatus.completed}),
    EnrolmentStatus.suspended: frozenset({EnrolmentStatus.active, EnrolmentStatus.withdrawn}),
    EnrolmentStatus.withdrawn: frozenset(),
    EnrolmentStatus.completed: frozenset(),
}


@dataclass
class EnrolmentFilters:
    course_id: uuid.UUID | None = None
    student_membership_id: uuid.UUID | None = None
    status: EnrolmentStatus | None = None
    academic_year: str | None = None


def _base(institution_id: uuid.UUID) -> Select:
    return (
        select(Enrolment, Membership, User, Course)
        .join(
            Membership,
            (Membership.id == Enrolment.student_membership_id) & (Membership.institution_id == Enrolment.institution_id),
        )
        .join(User, User.id == Membership.user_id)
        .join(Course, (Course.id == Enrolment.course_id) & (Course.institution_id == Enrolment.institution_id))
        .where(Enrolment.institution_id == institution_id)
    )


def scope(query: Select, tenant: TenantContext) -> Select:
    """Restrict a query on Enrolment to what the caller may see."""
    if tenant.role == MembershipRole.college_admin:
        return query
    if tenant.role == MembershipRole.student:
        return query.where(Enrolment.student_membership_id == tenant.membership.id)
    if tenant.role == MembershipRole.faculty:
        return query.where(_taught_by(tenant.membership.id))
    raise forbidden("insufficient_role", "Your role does not allow access to enrolment records")


def _taught_by(faculty_membership_id: uuid.UUID):
    """The explicit grant: an active assignment for the enrolment's course and period."""
    return exists().where(
        FacultyAssignment.institution_id == Enrolment.institution_id,
        FacultyAssignment.faculty_membership_id == faculty_membership_id,
        FacultyAssignment.status == AssignmentStatus.active,
        FacultyAssignment.course_id == Enrolment.course_id,
        FacultyAssignment.academic_year == Enrolment.academic_year,
        FacultyAssignment.academic_period == Enrolment.academic_period,
    )


def to_out(row) -> EnrolmentOut:
    enrolment, membership, user, course = row
    return EnrolmentOut(
        id=enrolment.id,
        student=PersonRef(membership_id=membership.id, user_id=user.id, full_name=user.full_name, email=user.email),
        course=CourseRef(id=course.id, name=course.name, code=course.code, status=course.status),
        academic_year=enrolment.academic_year,
        academic_period=enrolment.academic_period,
        status=enrolment.status,
        enrolled_at=enrolment.enrolled_at,
        completed_at=enrolment.completed_at,
        withdrawn_at=enrolment.withdrawn_at,
        created_at=enrolment.created_at,
        updated_at=enrolment.updated_at,
    )


def _apply_filters(query: Select, filters: EnrolmentFilters) -> Select:
    if filters.course_id is not None:
        query = query.where(Enrolment.course_id == filters.course_id)
    if filters.student_membership_id is not None:
        query = query.where(Enrolment.student_membership_id == filters.student_membership_id)
    if filters.status is not None:
        query = query.where(Enrolment.status == filters.status)
    if filters.academic_year is not None:
        query = query.where(Enrolment.academic_year == filters.academic_year)
    return query


def list_enrolments(
    db: Session, tenant: TenantContext, filters: EnrolmentFilters, *, limit: int, offset: int
) -> list[EnrolmentOut]:
    query = _apply_filters(scope(_base(tenant.institution_id), tenant), filters)
    query = query.order_by(Course.code, User.full_name, Enrolment.enrolled_at.desc(), Enrolment.id)
    return [to_out(row) for row in db.execute(query.limit(limit).offset(offset))]


def my_enrolments(db: Session, tenant: TenantContext, status: EnrolmentStatus | None) -> list[EnrolmentOut]:
    """The caller's own enrolments, whatever their role (normally students)."""
    query = _base(tenant.institution_id).where(Enrolment.student_membership_id == tenant.membership.id)
    if status is not None:
        query = query.where(Enrolment.status == status)
    return [to_out(row) for row in db.execute(query.order_by(Enrolment.enrolled_at.desc(), Enrolment.id))]


def get_enrolment(db: Session, tenant: TenantContext, enrolment_id: uuid.UUID) -> EnrolmentOut:
    try:
        query = scope(_base(tenant.institution_id), tenant)
    except ApiError:  # role without any enrolment scope
        raise not_found("enrolment", "Enrolment") from None
    row = db.execute(query.where(Enrolment.id == enrolment_id)).one_or_none()
    if row is None:
        raise not_found("enrolment", "Enrolment")
    return to_out(row)


def list_course_enrolments(
    db: Session, tenant: TenantContext, course_id: uuid.UUID, status: EnrolmentStatus | None, *, limit: int, offset: int
) -> list[EnrolmentOut]:
    """Course roster: admins, or faculty explicitly scoped to the course."""
    if tenant.role == MembershipRole.student:
        raise forbidden("insufficient_role", "Your role does not allow access to course rosters")
    query = scope(_base(tenant.institution_id), tenant).where(Enrolment.course_id == course_id)
    if not db.scalar(select(Course.id).where(Course.institution_id == tenant.institution_id, Course.id == course_id)):
        raise not_found("course", "Course")
    if tenant.role == MembershipRole.faculty and not db.scalar(
        select(FacultyAssignment.id)
        .where(
            FacultyAssignment.institution_id == tenant.institution_id,
            FacultyAssignment.course_id == course_id,
            FacultyAssignment.faculty_membership_id == tenant.membership.id,
            FacultyAssignment.status == AssignmentStatus.active,
        )
        .limit(1)
    ):
        raise forbidden("not_assigned", "You are not assigned to teach in this course")
    if status is not None:
        query = query.where(Enrolment.status == status)
    query = query.order_by(User.full_name, Enrolment.enrolled_at.desc(), Enrolment.id)
    return [to_out(row) for row in db.execute(query.limit(limit).offset(offset))]


def _active_student(db: Session, institution_id: uuid.UUID, membership_id: uuid.UUID) -> Membership:
    # FOR SHARE: a concurrent role/status change waits until this commits.
    membership = db.scalar(
        select(Membership)
        .where(Membership.institution_id == institution_id, Membership.id == membership_id)
        .with_for_update(read=True, of=Membership)  # not the eager-joined institution
    )
    if membership is None:
        raise not_found("student", "Student")
    if membership.role != MembershipRole.student or membership.status != MembershipStatus.active:
        raise conflict("not_an_active_student", "Only active student members can be enrolled")
    return membership


def _reload(db: Session, institution_id: uuid.UUID, enrolment_id: uuid.UUID) -> EnrolmentOut:
    return to_out(db.execute(_base(institution_id).where(Enrolment.id == enrolment_id)).one())


def _flush(db: Session) -> None:
    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        if constraint_name(exc) == "uq_enrolments_open":
            raise conflict(
                "enrolment_exists", "The student already has an open enrolment in this course for this period"
            ) from None
        raise


def create_enrolment(db: Session, institution_id: uuid.UUID, data: EnrolmentCreate) -> EnrolmentOut:
    _active_student(db, institution_id, data.student_membership_id)
    course = db.scalar(
        select(Course).where(Course.institution_id == institution_id, Course.id == data.course_id).with_for_update(read=True)
    )
    if course is None:
        raise not_found("course", "Course")
    if course.status != AcademicStatus.active:
        raise conflict("course_archived", "Students cannot be enrolled in an archived course")

    enrolment = Enrolment(institution_id=institution_id, **data.model_dump())
    db.add(enrolment)
    _flush(db)
    db.commit()
    return _reload(db, institution_id, enrolment.id)


def update_status(db: Session, institution_id: uuid.UUID, enrolment_id: uuid.UUID, status: EnrolmentStatus) -> EnrolmentOut:
    enrolment = db.scalar(
        select(Enrolment).where(Enrolment.institution_id == institution_id, Enrolment.id == enrolment_id).with_for_update()
    )
    if enrolment is None:
        raise not_found("enrolment", "Enrolment")
    if status != enrolment.status:
        if status not in TRANSITIONS[enrolment.status]:
            raise conflict(
                "invalid_status_transition", f"An enrolment cannot move from {enrolment.status.value} to {status.value}"
            )
        if status == EnrolmentStatus.active:  # reactivation: the student must still be eligible
            _active_student(db, institution_id, enrolment.student_membership_id)
        now = utcnow()
        enrolment.status = status
        if status == EnrolmentStatus.withdrawn:
            enrolment.withdrawn_at = now
        elif status == EnrolmentStatus.completed:
            enrolment.completed_at = now
        _flush(db)
        db.commit()
    return _reload(db, institution_id, enrolment.id)
