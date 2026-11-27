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
