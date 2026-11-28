import enum


class InstitutionStatus(str, enum.Enum):
    active = "active"
    suspended = "suspended"
    archived = "archived"


class MembershipRole(str, enum.Enum):
    """Roles held *within* an institution. platform_admin is not here: it is
    a platform-wide flag on the user, never granted through a membership."""

    student = "student"
    faculty = "faculty"
    college_admin = "college_admin"


class MembershipStatus(str, enum.Enum):
    active = "active"
    suspended = "suspended"


class AcademicStatus(str, enum.Enum):
    """Lifecycle of catalogue records (courses, subjects, rooms). Archiving
    replaces deletion: archived rows stay referenced by history."""

    active = "active"
    archived = "archived"


class DegreeLevel(str, enum.Enum):
    certificate = "certificate"
    diploma = "diploma"
    associate = "associate"
    bachelor = "bachelor"
    master = "master"
    doctorate = "doctorate"
    other = "other"


class EnrolmentStatus(str, enum.Enum):
    """active/suspended are "open"; withdrawn/completed are terminal history."""

    active = "active"
    suspended = "suspended"
    withdrawn = "withdrawn"
    completed = "completed"


class AssignmentStatus(str, enum.Enum):
    active = "active"
    ended = "ended"


class SessionStatus(str, enum.Enum):
    scheduled = "scheduled"
    cancelled = "cancelled"


class PublicationStatus(str, enum.Enum):
    """Shared lifecycle of authored content (resources, coursework,
    announcements): draft -> published -> archived; draft -> archived."""

    draft = "draft"
    published = "published"
    archived = "archived"


class ResourceType(str, enum.Enum):
    pdf = "pdf"
    document = "document"
    presentation = "presentation"
    video = "video"
    link = "link"
    note = "note"


class LatePolicy(str, enum.Enum):
    """What happens after the deadline."""

    reject = "reject"  # no submissions after due_at
    accept = "accept"  # accepted, flagged late
    accept_until = "accept_until"  # accepted and flagged late until late_cutoff_at


class AnnouncementPriority(str, enum.Enum):
    normal = "normal"
    important = "important"
    urgent = "urgent"


class AnnouncementAudience(str, enum.Enum):
    """Who an announcement is for, resolved from existing relationships:
    institution       every member
    course            students enrolled in the course + faculty teaching in it
    subject           students enrolled in the subject's course + its faculty
    subject_students  students enrolled in the subject's course only
    (Enrolment is per course, so "enrolled in a subject" means enrolled in
    the course that owns it.) College admins see every published one."""

    institution = "institution"
    course = "course"
    subject = "subject"
    subject_students = "subject_students"
