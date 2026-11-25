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
