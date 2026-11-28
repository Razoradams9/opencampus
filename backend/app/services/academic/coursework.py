"""Assignments, submissions and grading (M4.5).

Visibility of assignments:
  college_admin  all in the institution
  faculty        all (any status) of subjects they teach
  student        published, already available, in a course they are actively
                 enrolled in; archived ones only if they submitted to them
Submissions: a student sees only their own; managers (admin, or faculty
teaching the subject) see all for their assignments. Submissions and grades
are append-only (see models/coursework.py).
"""

import uuid
from datetime import datetime

from sqlalchemy import Select, and_, distinct, exists, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, aliased

from app.api.deps import TenantContext
from app.core.errors import ApiError, forbidden
from app.core.security import utcnow
from app.models import (
    AcademicStatus,
    Assignment,
    Course,
    LatePolicy,
    Membership,
    MembershipRole,
    PublicationStatus,
    Subject,
    Submission,
    SubmissionGrade,
    User,
)
from app.schemas.academic import (
    AssignmentWorkCreate,
    AssignmentWorkOut,
    AssignmentWorkUpdate,
    CourseRef,
    GradeCreate,
    GradeOut,
    PersonRef,
    StudentProgress,
    SubjectRef,
    SubmissionCreate,
    SubmissionOut,
    TeacherRef,
    check_assignment_dates,
)
from app.services.academic import access
from app.services.academic.common import conflict, constraint_name, not_found
from app.services.storage import get_file_storage

Author = aliased(Membership, name="author")
AuthorUser = aliased(User, name="author_user")


def window(assignment: Assignment, now: datetime) -> str:
    """not_open | open | late (accepted, flagged) | closed."""
    if now < assignment.available_from:
        return "not_open"
    if now <= assignment.due_at:
        return "open"
    if assignment.late_policy == LatePolicy.accept:
        return "late"
    if assignment.late_policy == LatePolicy.accept_until and assignment.late_cutoff_at and now <= assignment.late_cutoff_at:
        return "late"
    return "closed"


def _base(institution_id: uuid.UUID) -> Select:
    return (
        select(Assignment, Course, Subject, Author.id, AuthorUser.full_name)
        .join(Course, and_(Course.institution_id == Assignment.institution_id, Course.id == Assignment.course_id))
        .join(Subject, and_(Subject.institution_id == Assignment.institution_id, Subject.id == Assignment.subject_id))
        .join(Author, and_(Author.institution_id == Assignment.institution_id, Author.id == Assignment.created_by_membership_id))
        .join(AuthorUser, AuthorUser.id == Author.user_id)
        .where(Assignment.institution_id == institution_id)
    )


def _student_condition(membership_id: uuid.UUID, now: datetime):
    own_submission = exists().where(
        Submission.institution_id == Assignment.institution_id,
        Submission.assignment_id == Assignment.id,
        Submission.student_membership_id == membership_id,
    )
    return and_(
        access.enrolled_in_course(membership_id, Assignment.institution_id, Assignment.course_id),
        Assignment.available_from <= now,
        or_(
            Assignment.status == PublicationStatus.published,
            and_(Assignment.status == PublicationStatus.archived, own_submission),
        ),
    )


def _visible(query: Select, tenant: TenantContext, now: datetime) -> Select:
    if access.is_admin(tenant):
        return query
    if tenant.role == MembershipRole.faculty:
        return query.where(access.teaches_subject(tenant.membership.id, Assignment.institution_id, Assignment.subject_id))
    return query.where(_student_condition(tenant.membership.id, now))


# ---- Output -------------------------------------------------------------------


def _grades_for(db: Session, institution_id: uuid.UUID, submission_ids: list[uuid.UUID]) -> dict[uuid.UUID, list[GradeOut]]:
    if not submission_ids:
        return {}
    Grader = aliased(Membership)
    rows = db.execute(
        select(SubmissionGrade, Grader.id, User.full_name)
        .join(Grader, and_(Grader.institution_id == SubmissionGrade.institution_id, Grader.id == SubmissionGrade.graded_by_membership_id))
        .join(User, User.id == Grader.user_id)
        .where(SubmissionGrade.institution_id == institution_id, SubmissionGrade.submission_id.in_(submission_ids))
        .order_by(SubmissionGrade.graded_at, SubmissionGrade.id)
    )
    result: dict[uuid.UUID, list[GradeOut]] = {}
    for grade, grader_id, grader_name in rows:
        result.setdefault(grade.submission_id, []).append(
            GradeOut(
                marks_awarded=float(grade.marks_awarded),
                feedback=grade.feedback,
                graded_at=grade.graded_at,
                graded_by=TeacherRef(membership_id=grader_id, full_name=grader_name),
            )
        )
    return result


def _progress(db: Session, tenant: TenantContext, assignment_ids: list[uuid.UUID]) -> dict[uuid.UUID, StudentProgress]:
    subs = db.scalars(
        select(Submission)
        .where(
            Submission.institution_id == tenant.institution_id,
            Submission.student_membership_id == tenant.membership.id,
            Submission.assignment_id.in_(assignment_ids),
        )
        .order_by(Submission.assignment_id, Submission.attempt)
    ).all()
    latest: dict[uuid.UUID, Submission] = {}
    attempts: dict[uuid.UUID, int] = {}
    for sub in subs:
        latest[sub.assignment_id] = sub
        attempts[sub.assignment_id] = attempts.get(sub.assignment_id, 0) + 1
    grades = _grades_for(db, tenant.institution_id, [s.id for s in latest.values()])
    result = {}
    for assignment_id in assignment_ids:
        sub = latest.get(assignment_id)
        grade = grades.get(sub.id, [None])[-1] if sub else None
        result[assignment_id] = StudentProgress(
            status="graded" if grade else "submitted" if sub else "not_submitted",
            attempts=attempts.get(assignment_id, 0),
            last_submitted_at=sub.submitted_at if sub else None,
            is_late=sub.is_late if sub else False,
            grade=grade,
        )
    return result


def _counts(db: Session, institution_id: uuid.UUID, assignment_ids: list[uuid.UUID]) -> dict[uuid.UUID, tuple[int, int]]:
    if not assignment_ids:
        return {}
    submitted = dict(
        db.execute(
            select(Submission.assignment_id, func.count(distinct(Submission.student_membership_id)))
            .where(Submission.institution_id == institution_id, Submission.assignment_id.in_(assignment_ids))
            .group_by(Submission.assignment_id)
        ).all()
    )
    graded = dict(
        db.execute(
            select(Submission.assignment_id, func.count(distinct(Submission.student_membership_id)))
            .join(SubmissionGrade, and_(SubmissionGrade.institution_id == Submission.institution_id, SubmissionGrade.submission_id == Submission.id))
            .where(Submission.institution_id == institution_id, Submission.assignment_id.in_(assignment_ids))
            .group_by(Submission.assignment_id)
        ).all()
    )
    return {a: (submitted.get(a, 0), graded.get(a, 0)) for a in assignment_ids}


def _outs(db: Session, tenant: TenantContext, rows, now: datetime) -> list[AssignmentWorkOut]:
    rows = list(rows)
    ids = [r[0].id for r in rows]
    student = tenant.role == MembershipRole.student
    progress = _progress(db, tenant, ids) if student else {}
    counts = {} if student else _counts(db, tenant.institution_id, ids)
    result = []
    for assignment, course, subject, author_id, author_name in rows:
        submitted, graded = counts.get(assignment.id, (None, None))
        result.append(
            AssignmentWorkOut(
                id=assignment.id,
                course=CourseRef(id=course.id, name=course.name, code=course.code, status=course.status),
                subject=SubjectRef(id=subject.id, name=subject.name, code=subject.code, semester=subject.semester, credits=float(subject.credits)),
                title=assignment.title,
                instructions=assignment.instructions,
                reference_url=assignment.reference_url,
                available_from=assignment.available_from,
                due_at=assignment.due_at,
                late_policy=assignment.late_policy,
                late_cutoff_at=assignment.late_cutoff_at,
                max_marks=float(assignment.max_marks),
                status=assignment.status,
                published_at=assignment.published_at,
                created_by=TeacherRef(membership_id=author_id, full_name=author_name),
                window=window(assignment, now),
                me=progress.get(assignment.id),
                submitted_students=submitted,
                graded_students=graded,
                created_at=assignment.created_at,
                updated_at=assignment.updated_at,
            )
        )
    return result


# ---- Assignments -------------------------------------------------------------


def list_mine(db: Session, tenant: TenantContext) -> list[AssignmentWorkOut]:
    """Student view: assignments of their active enrolments, by deadline."""
    now = utcnow()
    query = _base(tenant.institution_id).where(_student_condition(tenant.membership.id, now))
    return _outs(db, tenant, db.execute(query.order_by(Assignment.due_at, Assignment.id)), now)


def list_managed(db: Session, tenant: TenantContext, subject_id, status, *, limit: int, offset: int) -> list[AssignmentWorkOut]:
    if not (access.is_admin(tenant) or tenant.role == MembershipRole.faculty):
        raise forbidden("insufficient_role", "Only faculty and administrators manage assignments")
    now = utcnow()
    query = _visible(_base(tenant.institution_id), tenant, now)
    if subject_id is not None:
        query = query.where(Assignment.subject_id == subject_id)
    if status is not None:
        query = query.where(Assignment.status == status)
    query = query.order_by(Assignment.due_at.desc(), Assignment.id).limit(limit).offset(offset)
    return _outs(db, tenant, db.execute(query), now)


def list_for_subject(db: Session, tenant: TenantContext, subject_id: uuid.UUID) -> list[AssignmentWorkOut]:
    subject, course = access.subject_with_course(db, tenant.institution_id, subject_id)
    if not (access.can_manage_subject(db, tenant, subject.id) or access.can_study_course(db, tenant, course.id)):
        raise forbidden("not_enrolled_or_assigned", "You are not enrolled in or teaching this subject")
    now = utcnow()
    query = _visible(_base(tenant.institution_id), tenant, now).where(Assignment.subject_id == subject.id)
    return _outs(db, tenant, db.execute(query.order_by(Assignment.due_at, Assignment.id)), now)


def get(db: Session, tenant: TenantContext, assignment_id: uuid.UUID) -> AssignmentWorkOut:
    now = utcnow()
    row = db.execute(_visible(_base(tenant.institution_id), tenant, now).where(Assignment.id == assignment_id)).one_or_none()
    if row is None:
        raise not_found("assignment", "Assignment")
    return _outs(db, tenant, [row], now)[0]


def _reload(db: Session, tenant: TenantContext, assignment_id: uuid.UUID) -> AssignmentWorkOut:
    return _outs(db, tenant, [db.execute(_base(tenant.institution_id).where(Assignment.id == assignment_id)).one()], utcnow())[0]


def create(db: Session, tenant: TenantContext, subject_id: uuid.UUID, data: AssignmentWorkCreate) -> AssignmentWorkOut:
    subject, course = access.subject_with_course(db, tenant.institution_id, subject_id)
    access.require_manage_subject(db, tenant, subject.id)
    if subject.status != AcademicStatus.active or course.status != AcademicStatus.active:
        raise conflict("subject_archived", "The subject or its course is archived")
    assignment = Assignment(
        institution_id=tenant.institution_id,
        course_id=course.id,
        subject_id=subject.id,
        created_by_membership_id=tenant.membership.id,
        **data.model_dump(),
    )
    db.add(assignment)
    db.flush()
    db.commit()
    return _reload(db, tenant, assignment.id)


def _manageable(db: Session, tenant: TenantContext, assignment_id: uuid.UUID, *, lock: bool = True) -> Assignment:
    query = select(Assignment).where(Assignment.institution_id == tenant.institution_id, Assignment.id == assignment_id)
    assignment = db.scalar(query.with_for_update() if lock else query)
    if assignment is None:
        raise not_found("assignment", "Assignment")
    if not access.can_manage_subject(db, tenant, assignment.subject_id):
        if tenant.role == MembershipRole.faculty:
            raise forbidden("not_assigned", "You are not assigned to teach this subject")
        if tenant.role == MembershipRole.student:
            # Students may know the assignment; they still cannot manage it.
            raise forbidden("insufficient_role", "Students cannot manage assignments")
        raise not_found("assignment", "Assignment")
    return assignment


def update(db: Session, tenant: TenantContext, assignment_id: uuid.UUID, data: AssignmentWorkUpdate) -> AssignmentWorkOut:
    assignment = _manageable(db, tenant, assignment_id)
    if assignment.status == PublicationStatus.archived:
        raise conflict("assignment_archived", "Archived assignments are read-only")
    changes = data.changes()
    merged = {k: changes.get(k, getattr(assignment, k)) for k in ("available_from", "due_at", "late_policy", "late_cutoff_at")}
    try:
        check_assignment_dates(merged["available_from"], merged["due_at"], LatePolicy(merged["late_policy"]), merged["late_cutoff_at"])
    except ValueError as exc:
        raise ApiError(422, "invalid_dates", str(exc)) from None
    if "max_marks" in changes:
        highest = db.scalar(
            select(func.max(SubmissionGrade.marks_awarded))
            .join(Submission, and_(Submission.institution_id == SubmissionGrade.institution_id, Submission.id == SubmissionGrade.submission_id))
            .where(Submission.institution_id == tenant.institution_id, Submission.assignment_id == assignment.id)
        )
        if highest is not None and changes["max_marks"] < highest:
            raise conflict("max_marks_below_grades", f"A submission was already awarded {highest} marks")
    for name, value in changes.items():
        setattr(assignment, name, value)
    db.flush()
    db.commit()
    return _reload(db, tenant, assignment.id)


def set_status(db: Session, tenant: TenantContext, assignment_id: uuid.UUID, status: PublicationStatus) -> AssignmentWorkOut:
    assignment = _manageable(db, tenant, assignment_id)
    if status == PublicationStatus.published:
        if assignment.status == PublicationStatus.archived:
            raise conflict("assignment_archived", "Archived assignments cannot be republished")
        assignment.published_at = assignment.published_at or utcnow()
    assignment.status = status
    db.flush()
    db.commit()
    return _reload(db, tenant, assignment.id)


# ---- Submissions -------------------------------------------------------------

Student = aliased(Membership, name="student")


def _submission_base(institution_id: uuid.UUID) -> Select:
    return (
        select(Submission, Student.id, User.id, User.full_name, User.email)
        .join(Student, and_(Student.institution_id == Submission.institution_id, Student.id == Submission.student_membership_id))
        .join(User, User.id == Student.user_id)
        .where(Submission.institution_id == institution_id)
    )


def _submission_outs(db: Session, institution_id: uuid.UUID, rows) -> list[SubmissionOut]:
    rows = list(rows)
    grades = _grades_for(db, institution_id, [r[0].id for r in rows])
    # Highest attempt per (assignment, student) among *all* stored attempts.
    keys = {(r[0].assignment_id, r[0].student_membership_id) for r in rows}
    latest: dict[tuple, int] = {}
    if keys:
        for assignment_id, student_id, top in db.execute(
            select(Submission.assignment_id, Submission.student_membership_id, func.max(Submission.attempt))
            .where(Submission.institution_id == institution_id, Submission.assignment_id.in_({k[0] for k in keys}))
            .group_by(Submission.assignment_id, Submission.student_membership_id)
        ):
            latest[(assignment_id, student_id)] = top
    storage = get_file_storage() is not None
    out = []
    for sub, membership_id, user_id, name, email in rows:
        history = grades.get(sub.id, [])
        superseded = sub.attempt < latest.get((sub.assignment_id, sub.student_membership_id), sub.attempt)
        out.append(
            SubmissionOut(
                id=sub.id,
                assignment_id=sub.assignment_id,
                student=PersonRef(membership_id=membership_id, user_id=user_id, full_name=name, email=email),
                attempt=sub.attempt,
                body=sub.body,
                file_available=bool(sub.storage_key) and storage,
                submitted_at=sub.submitted_at,
                is_late=sub.is_late,
                status="superseded" if superseded else "graded" if history else "submitted",
                grade=history[-1] if history else None,
                grade_history=history,
            )
        )
    return out


def submit(db: Session, tenant: TenantContext, assignment_id: uuid.UUID, data: SubmissionCreate) -> SubmissionOut:
    if tenant.role != MembershipRole.student:
        raise forbidden("insufficient_role", "Only students submit work")
    now = utcnow()
    # FOR SHARE: a concurrent archive or deadline change waits for this insert.
    assignment = db.scalar(
        select(Assignment)
        .where(Assignment.institution_id == tenant.institution_id, Assignment.id == assignment_id, _student_condition(tenant.membership.id, now))
        .with_for_update(read=True, of=Assignment)
    )
    if assignment is None:
        raise not_found("assignment", "Assignment")
    if assignment.status != PublicationStatus.published:
        raise conflict("assignment_closed", "This assignment is no longer accepting submissions")
    state = window(assignment, now)
    if state == "not_open":
        raise conflict("assignment_not_open", "This assignment is not open for submissions yet")
    if state == "closed":
        raise conflict("deadline_passed", "The deadline has passed and late submissions are not accepted")
    attempt = (
        db.scalar(
            select(func.max(Submission.attempt)).where(
                Submission.institution_id == tenant.institution_id,
                Submission.assignment_id == assignment.id,
                Submission.student_membership_id == tenant.membership.id,
            )
        )
        or 0
    ) + 1
    submission = Submission(
        institution_id=tenant.institution_id,
        assignment_id=assignment.id,
        student_membership_id=tenant.membership.id,
        attempt=attempt,
        body=data.body,
        submitted_at=now,
        is_late=state == "late",
    )
    db.add(submission)
    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        if constraint_name(exc) == "uq_submissions_attempt":
            raise conflict("submission_in_progress", "Another submission was saved at the same moment; reload and try again") from None
        raise
    db.commit()
    return my_submissions(db, tenant, assignment.id)[-1]


def my_submissions(db: Session, tenant: TenantContext, assignment_id: uuid.UUID) -> list[SubmissionOut]:
    """The caller's own attempts for an assignment, oldest first."""
    get(db, tenant, assignment_id)  # 404 unless visible to the caller
    query = _submission_base(tenant.institution_id).where(
        Submission.assignment_id == assignment_id, Submission.student_membership_id == tenant.membership.id
    )
    return _submission_outs(db, tenant.institution_id, db.execute(query.order_by(Submission.attempt)))


def assignment_submissions(db: Session, tenant: TenantContext, assignment_id: uuid.UUID, latest_only: bool) -> list[SubmissionOut]:
    assignment = _manageable(db, tenant, assignment_id, lock=False)
    query = _submission_base(tenant.institution_id).where(Submission.assignment_id == assignment.id)
    if latest_only:
        newer = aliased(Submission)
        query = query.where(
            ~exists().where(
                newer.institution_id == Submission.institution_id,
                newer.assignment_id == Submission.assignment_id,
                newer.student_membership_id == Submission.student_membership_id,
                newer.attempt > Submission.attempt,
            )
        )
    query = query.order_by(User.full_name, Submission.student_membership_id, Submission.attempt.desc())
    return _submission_outs(db, tenant.institution_id, db.execute(query))


def _submission_row(db: Session, tenant: TenantContext, submission_id: uuid.UUID):
    row = db.execute(_submission_base(tenant.institution_id).where(Submission.id == submission_id)).one_or_none()
    if row is None:
        raise not_found("submission", "Submission")
    return row


def get_submission(db: Session, tenant: TenantContext, submission_id: uuid.UUID) -> SubmissionOut:
    row = _submission_row(db, tenant, submission_id)
    submission = row[0]
    own = submission.student_membership_id == tenant.membership.id
    if not own:
        assignment = db.get(Assignment, submission.assignment_id)
        if assignment is None or not access.can_manage_subject(db, tenant, assignment.subject_id):
            raise not_found("submission", "Submission")  # another student's work: indistinguishable from missing
    return _submission_outs(db, tenant.institution_id, [row])[0]


def grade(db: Session, tenant: TenantContext, submission_id: uuid.UUID, data: GradeCreate) -> SubmissionOut:
    if tenant.role == MembershipRole.student:
        raise forbidden("insufficient_role", "Students cannot grade work")
    submission = _submission_row(db, tenant, submission_id)[0]
    # Lock the assignment: a concurrent max_marks change cannot slip under this grade.
    assignment = _manageable(db, tenant, submission.assignment_id)
    if data.marks_awarded > assignment.max_marks:
        raise ApiError(422, "marks_exceed_maximum", f"Marks cannot exceed the maximum of {assignment.max_marks}")
    db.add(
        SubmissionGrade(
            institution_id=tenant.institution_id,
            submission_id=submission.id,
            graded_by_membership_id=tenant.membership.id,
            marks_awarded=data.marks_awarded,
            feedback=data.feedback.strip() if data.feedback and data.feedback.strip() else None,
            graded_at=utcnow(),
        )
    )
    db.flush()
    db.commit()
    return _submission_outs(db, tenant.institution_id, [_submission_row(db, tenant, submission.id)])[0]
