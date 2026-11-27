"""Courses and subjects (M4.1)."""

import uuid

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import AcademicStatus, Course, Subject
from app.schemas.academic import CourseCreate, CourseUpdate, SubjectCreate, SubjectUpdate
from app.services.academic.common import conflict, constraint_name, not_found

_CONSTRAINT_ERRORS = {
    "uq_courses_institution_code": ("course_code_taken", "A course with this code already exists"),
    "uq_subjects_course_code": ("subject_code_taken", "This course already has a subject with this code"),
}


def _flush(db: Session) -> None:
    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        known = _CONSTRAINT_ERRORS.get(constraint_name(exc) or "")
        if known:
            raise conflict(*known) from None
        raise


# ---- Courses ---------------------------------------------------------------


def list_courses(
    db: Session, institution_id: uuid.UUID, *, status: AcademicStatus | None, limit: int, offset: int
) -> list[Course]:
    query = select(Course).where(Course.institution_id == institution_id)
    if status is not None:
        query = query.where(Course.status == status)
    return list(db.scalars(query.order_by(Course.code).limit(limit).offset(offset)))


def get_course(
    db: Session, institution_id: uuid.UUID, course_id: uuid.UUID, *, active_only: bool = False, lock: bool = False
) -> Course:
    query = select(Course).where(Course.institution_id == institution_id, Course.id == course_id)
    if lock:
        query = query.with_for_update()
    course = db.scalar(query)
    if course is None or (active_only and course.status != AcademicStatus.active):
        raise not_found("course", "Course")
    return course


def create_course(db: Session, institution_id: uuid.UUID, data: CourseCreate) -> Course:
    course = Course(institution_id=institution_id, **data.model_dump())
    db.add(course)
    _flush(db)
    db.commit()
    return course


def update_course(db: Session, institution_id: uuid.UUID, course_id: uuid.UUID, data: CourseUpdate) -> Course:
    # Lock: a concurrent subject insert validates its semester against this row.
    course = get_course(db, institution_id, course_id, lock=True)
    changes = data.changes()
    duration = changes.get("duration_semesters")
    if duration is not None and duration < course.duration_semesters:
        highest = db.scalar(
            select(func.max(Subject.semester)).where(Subject.institution_id == institution_id, Subject.course_id == course.id)
        )
        if highest is not None and highest > duration:
            raise conflict(
                "duration_below_subjects", f"Subjects exist in semester {highest}; the course cannot be shorter than that"
            )
    for name, value in changes.items():
        setattr(course, name, value)
    _flush(db)
    db.commit()
    return course


def set_course_status(db: Session, institution_id: uuid.UUID, course_id: uuid.UUID, status: AcademicStatus) -> Course:
    """Archive or restore. Subjects keep their own status; history (enrolments,
    sessions) keeps referencing the course either way."""
    course = get_course(db, institution_id, course_id, lock=True)
    course.status = status
    db.flush()
    db.commit()
    return course


# ---- Subjects --------------------------------------------------------------


def list_subjects(
    db: Session, institution_id: uuid.UUID, course_id: uuid.UUID, *, status: AcademicStatus | None, active_course_only: bool
) -> list[Subject]:
    get_course(db, institution_id, course_id, active_only=active_course_only)
    query = select(Subject).where(Subject.institution_id == institution_id, Subject.course_id == course_id)
    if status is not None:
        query = query.where(Subject.status == status)
    return list(db.scalars(query.order_by(Subject.semester, Subject.code)))


def get_subject(
    db: Session, institution_id: uuid.UUID, subject_id: uuid.UUID, *, active_only: bool = False
) -> Subject:
    subject = db.scalar(select(Subject).where(Subject.institution_id == institution_id, Subject.id == subject_id))
    if subject is None:
        raise not_found("subject", "Subject")
    if active_only:
        course = db.get(Course, subject.course_id)
        if subject.status != AcademicStatus.active or course is None or course.status != AcademicStatus.active:
            raise not_found("subject", "Subject")
    return subject


def _check_semester(course: Course, semester: int) -> None:
    if semester > course.duration_semesters:
        raise conflict(
            "semester_out_of_range",
            f"Semester {semester} is beyond this course's {course.duration_semesters} semesters",
        )


def create_subject(db: Session, institution_id: uuid.UUID, course_id: uuid.UUID, data: SubjectCreate) -> Subject:
    course = get_course(db, institution_id, course_id, lock=True)
    if course.status != AcademicStatus.active:
        raise conflict("course_archived", "Subjects cannot be added to an archived course")
    _check_semester(course, data.semester)
    subject = Subject(institution_id=institution_id, course_id=course.id, **data.model_dump())
    db.add(subject)
    _flush(db)
    db.commit()
    return subject


def update_subject(db: Session, institution_id: uuid.UUID, subject_id: uuid.UUID, data: SubjectUpdate) -> Subject:
    subject = get_subject(db, institution_id, subject_id)
    changes = data.changes()
    if "semester" in changes:
        _check_semester(get_course(db, institution_id, subject.course_id, lock=True), changes["semester"])
    for name, value in changes.items():
        setattr(subject, name, value)
    _flush(db)
    db.commit()
    return subject


def set_subject_status(db: Session, institution_id: uuid.UUID, subject_id: uuid.UUID, status: AcademicStatus) -> Subject:
    subject = get_subject(db, institution_id, subject_id)
    if status == AcademicStatus.active:
        course = get_course(db, institution_id, subject.course_id, lock=True)
        if course.status != AcademicStatus.active:
            raise conflict("course_archived", "Restore the course before restoring its subjects")
    subject.status = status
    db.flush()
    db.commit()
    return subject
