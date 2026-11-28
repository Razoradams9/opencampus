"""/api/academic: institution-scoped academic records (M4).

Every route depends on the tenant chain (get_principal -> get_tenant), so the
institution is the session's active one and RLS context is set before any
service runs. Responses do not depend on which client (student, faculty or
administration app) calls them; only the caller's membership role matters.
"""

from fastapi import APIRouter

from app.api.academic import announcements, courses, coursework, enrolments, resources, timetable

router = APIRouter(prefix="/academic", tags=["academic"])
router.include_router(courses.router)
router.include_router(enrolments.router)
router.include_router(timetable.router)
router.include_router(resources.router)
router.include_router(coursework.router)
router.include_router(announcements.router)
