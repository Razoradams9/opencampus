"""Shared authorisation rules for academic content (M4.4-M4.6).

Two grants exist, both read from the database, never from the request:
  * a student is "in" a course while they hold an ACTIVE enrolment in it;
  * a faculty member "teaches" a subject while they hold an ACTIVE faculty
    assignment for it (any academic period).
College admins manage everything in their institution. Platform admins have
no academic access except through a membership (see docs/academic.md).

Each rule exists as a SQL expression (for filtering lists) and as a check
(for single records), so lists and detail views cannot disagree.
"""

import uuid

from sqlalchemy import ColumnElement, exists, select
from sqlalchemy.orm import Session

from app.api.deps import TenantContext
from app.core.errors import forbidden
from app.models import (
    AssignmentStatus,
    Course,
    Enrolment,
    EnrolmentStatus,
    FacultyAssignment,
    MembershipRole,
    Subject,
)
from app.services.academic.common import not_found


def is_admin(tenant: TenantContext) -> bool:
    return tenant.role == MembershipRole.college_admin


def enrolled_in_course(membership_id: uuid.UUID, institution_col, course_col) -> ColumnElement[bool]:
    return exists().where(
        Enrolment.institution_id == institution_col,
        Enrolment.student_membership_id == membership_id,
        Enrolment.course_id == course_col,
        Enrolment.status == EnrolmentStatus.active,
    )


def teaches_subject(membership_id: uuid.UUID, institution_col, subject_col) -> ColumnElement[bool]:
    return exists().where(
        FacultyAssignment.institution_id == institution_col,
        FacultyAssignment.faculty_membership_id == membership_id,
        FacultyAssignment.subject_id == subject_col,
        FacultyAssignment.status == AssignmentStatus.active,
    )


def teaches_in_course(membership_id: uuid.UUID, institution_col, course_col) -> ColumnElement[bool]:
    return exists().where(
        FacultyAssignment.institution_id == institution_col,
        FacultyAssignment.faculty_membership_id == membership_id,
        FacultyAssignment.course_id == course_col,
        FacultyAssignment.status == AssignmentStatus.active,
    )


def can_manage_subject(db: Session, tenant: TenantContext, subject_id: uuid.UUID) -> bool:
    if is_admin(tenant):
        return True
    if tenant.role != MembershipRole.faculty:
        return False
    return bool(db.scalar(select(teaches_subject(tenant.membership.id, tenant.institution_id, subject_id))))


def can_study_course(db: Session, tenant: TenantContext, course_id: uuid.UUID) -> bool:
    if tenant.role != MembershipRole.student:
        return False
    return bool(db.scalar(select(enrolled_in_course(tenant.membership.id, tenant.institution_id, course_id))))


def subject_with_course(db: Session, institution_id: uuid.UUID, subject_id: uuid.UUID) -> tuple[Subject, Course]:
    row = db.execute(
        select(Subject, Course)
        .join(Course, (Course.institution_id == Subject.institution_id) & (Course.id == Subject.course_id))
        .where(Subject.institution_id == institution_id, Subject.id == subject_id)
    ).one_or_none()
    if row is None:
        raise not_found("subject", "Subject")
    return row[0], row[1]


def require_manage_subject(db: Session, tenant: TenantContext, subject_id: uuid.UUID) -> None:
    if not can_manage_subject(db, tenant, subject_id):
        raise forbidden("not_assigned", "You are not assigned to teach this subject")
