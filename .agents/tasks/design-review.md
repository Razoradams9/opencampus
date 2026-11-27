# Design Review — M4 Academic Batch (Revision 2)

**Reviewer:** Design Review Agent  
**Date:** 2026-11-26  
**Branch:** main  
**Design doc:** `.agents/tasks/design.md` (Revision 2, post-review)

---

## Summary

Revision 2 is substantially improved and resolves all 14 original blocking findings. The document is well-structured, explicit about cross-cutting conventions, and contains detailed code snippets. However, the cross-check against the actual repository and careful reading of the design reveals a set of new and residual issues that must be resolved before implementation begins.

**Verdict: CHANGES_REQUESTED** (4 HIGH, 6 MEDIUM findings)

---

## Findings

### HIGH

---

#### H-1 — `logout` is HTTP 204, not HTTP 200; archive convention claim is wrong

**Where:** Cross-Cutting Conventions → Archive operations section.

**Problem:** The design justifies the archive endpoint HTTP status code by analogy:  
> "This matches the platform's pattern of distinct mutating sub-resources for state transitions (compare `POST /api/auth/logout` → 200, `POST /api/auth/switch-institution` → 200)."

Verified against `app/api/auth.py`:
- `POST /api/auth/logout` → `HTTP 204 NO CONTENT` (not 200)
- `POST /api/auth/switch-institution` → `HTTP 200` ✓

The claim about `logout` is factually wrong. The design uses a false premise to justify a convention. This is a documentation error but it matters: a coder implementing from this document could use 204 for archive endpoints (matching logout) or 200 (matching switch-institution). The convention must be stated without relying on the incorrect `logout` analogy.

**Fix:** State the rule directly without the analogy:  
> "Archive and cancel endpoints return HTTP 200 with the updated resource body. No redirect, no 204."  
Remove the parenthetical comparison to `logout`.

---

#### H-2 — `get_tenant` does not check `membership.status == active` for the `memberships_select` RLS policy wording in M9

**Where:** M4.3 Service layer additions → `get_my_timetable` timetable query; and Review Findings Response → N9.

**Problem:** The design states:  
> "RLS on `memberships` selects by `institution_id = app_current_tenant()`, which is set for all authenticated requests. The join from `FacultyAssignment → Membership → User` traverses `memberships` within the tenant context — this is correct."

Verified against `0001_identity_and_tenancy.py`:  
```sql
CREATE POLICY memberships_select ON memberships FOR SELECT
USING (institution_id = app_current_tenant() OR user_id = app_current_user())
```

The `memberships` SELECT policy uses an **OR** (`institution_id = ... OR user_id = ...`). When `app_current_tenant()` is set to institution A, the policy returns all memberships of institution A **plus** every row where `user_id = app_current_user()` — which may include memberships in institutions B, C, etc.

The timetable query joins `FacultyAssignment → Membership` on `institution_id` and `id`. That join condition itself includes `Membership.institution_id == FacultyAssignment.institution_id`, so only the institution-matched branch fires in practice. The design's claim that this "works within tenant context" is correct for the query as written — but the reason given (RLS filters to institution_id) is imprecise; the cross-institution safety comes from the ORM `institution_id` join condition, not from the RLS policy alone.

The bigger real problem: the design's RLS claim for `memberships` in the timetable join is misleadingly stated. If a future implementor removes the explicit `institution_id` join condition trusting "RLS handles it," the query would leak cross-institution faculty names through the `OR user_id` branch. The design must explicitly document that the ORM join condition `Membership.institution_id == FacultyAssignment.institution_id` is the cross-institution guard on this join, not RLS alone.

**Fix:** In the M9 timetable query documentation, add an explicit note:  
> "The `institution_id` equality in the `Membership` join is the cross-institution guard for this traversal. The `memberships_select` RLS policy uses `institution_id = app_current_tenant() OR user_id = app_current_user()`, meaning RLS alone is not sufficient; the ORM join condition must be preserved."

---

#### H-3 — `EnrolmentCreate` accepts `student_membership_id` and `course_id` from the request body; `institution_id` enforcement rule is not fully applied here

**Where:** M4.2 → Schemas → `EnrolmentCreate`; Cross-Cutting Conventions → `institution_id` enforcement.

**Problem:** The design's cross-cutting rule states:  
> "`institution_id` is never accepted from request bodies. It is always taken from `tenant.institution_id` inside the service layer."

However, `EnrolmentCreate` accepts `student_membership_id` and `course_id` from the caller:

```python
class EnrolmentCreate(StrictModel):
    student_membership_id: uuid.UUID
    course_id: uuid.UUID
    academic_year: int = Field(ge=2000, le=2100)
    academic_period: str = Field(min_length=1, max_length=20)
```

The service then validates both against the institution using `institution_id` from the token. This is **structurally correct** — the validation sequence in `create_enrolment` explicitly fetches the membership and course by `(institution_id, id)`. But the cross-cutting rule as written says "never accepted from request bodies," without carving out this legitimate case. The design is therefore internally inconsistent: the convention description prohibits what the enrolment schema does.

Additionally, the design does not state what the API should return when a caller supplies a `student_membership_id` that exists in the DB but belongs to a different institution. The service does a `(institution_id, student_membership_id)` lookup and returns 404 — that is the correct and safe behavior — but it must be explicitly documented so it isn't accidentally changed to a 403 or 422 that leaks existence information.

**Fix 1:** Rephrase the cross-cutting rule as:  
> "`institution_id` is never accepted from, or derived from, any request body field. It is always taken from `tenant.institution_id`. UUID references to other tenant-owned objects (such as `student_membership_id`, `course_id`) are accepted from the body but are always re-validated against `institution_id` server-side; a mismatch returns 404, not 403."

**Fix 2:** Add to the M4.2 error table:  
| `create_enrolment` | `student_membership_id` or `course_id` exists but belongs to a different institution | 404 `membership_not_found` / `course_not_found` |

---

#### H-4 — `faculty_assignments` has no `updated_at` trigger in migration 0006 step list, but it also has no `updated_at` column — the design is internally inconsistent on this

**Where:** M4.3 → `faculty_assignments` table definition; M4.3 → Migration 0006 step list.

**Problem:** The table definition explicitly states "No `updated_at` — assignments are immutable." The migration step list says:

> "4. Create `faculty_assignments` table, indexes, partial unique index, RLS policies, grants."

No trigger is mentioned for `faculty_assignments`, which is consistent with the no-`updated_at` decision. However the SQLAlchemy model snippet does **not** show a `faculty_assignments` model at all — only the `ClassSession` model is shown. The design relies on the reader inferring the full `FacultyAssignment` ORM model. Without the model snippet, the coder has no authoritative source for:
- Whether `TimestampMixin` is applied (it must not be, since no `updated_at` is desired)
- Whether `created_at` is mapped directly with `server_default=func.now()` or via mixin
- The exact `__table_args__` tuple

The absence of the `FacultyAssignment` ORM model snippet is a gap that will cause implementation ambiguity. The partial unique index on `faculty_assignments` is defined only in the data model table description, not in an ORM `__table_args__` snippet.

**Fix:** Add the full `FacultyAssignment` SQLAlchemy ORM model snippet, including `__table_args__` with both composite `ForeignKeyConstraint` entries and the note that `TimestampMixin` is **not** used (instead `created_at` is mapped directly). Example minimum:

```python
class FacultyAssignment(Base):
    __tablename__ = "faculty_assignments"
    __table_args__ = (
        ForeignKeyConstraint(["institution_id", "course_id"],
                             ["courses.institution_id", "courses.id"],
                             name="fk_faculty_assignments_..."),
        ForeignKeyConstraint(["institution_id", "subject_id"],
                             ["subjects.institution_id", "subjects.id"],
                             name="fk_faculty_assignments_..."),
        ForeignKeyConstraint(["institution_id", "faculty_membership_id"],
                             ["memberships.institution_id", "memberships.id"],
                             name="fk_faculty_assignments_..."),
        # partial unique index created in migration, not here
    )
    ...
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    # NO updated_at — assignments are immutable
```

---

### MEDIUM

---

#### M-1 — `faculty_assignments` RLS policies: DELETE not granted but `cancel` operation sets `status = cancelled`; no delete grant vs. no physical delete is unspecified for this table

**Where:** M4.3 → Alembic migration 0006 → Grants.

**Problem:** The grants section states:  
> "GRANT SELECT, INSERT, UPDATE ON rooms, faculty_assignments, class_sessions TO `<app_role>`"

The cancel operation for faculty assignments sets `status = cancelled` via an UPDATE — no DELETE grant is required. This is correct. However, the design does not state whether a DELETE grant is explicitly withheld from `faculty_assignments` by design (like courses, subjects, enrolments) or simply omitted. Given that the design explicitly documents "no DELETE granted on academic tables" in the cross-cutting conventions and the rationale, the absence of an explicit DELETE-withheld note for each of the M4.3 tables (rooms, faculty_assignments, class_sessions) is an omission that creates implementer uncertainty about whether this was intentional.

The design also does not document whether cancelled `faculty_assignments` rows are ever physically cleaned up (e.g. via a future job). If they accumulate indefinitely, the partial unique index `uq_faculty_assignments_active` will continue to work correctly (it only prevents duplicate active rows), but the table will grow unboundedly. This should be documented as a known limitation.

**Fix:** Add a note under M4.3 grants:  
> "No DELETE is granted on `rooms`, `faculty_assignments`, or `class_sessions`. Cancellation and archiving are the only removal mechanisms. Cancelled `faculty_assignments` rows are retained indefinitely as historical record."

---

#### M-2 — `SessionUpdate` allows setting `status = "cancelled"` but the overlap-recheck logic described in `update_session` does not explicitly skip overlap checks when the status transition is to `cancelled`

**Where:** M4.3 → `update_session` service function description.

**Problem:** The design states for `update_session`:  
> "If `status = cancelled` requested: set status, flush, commit; skip overlap checks."

This is correct behavior and the design states it explicitly. However the `SessionUpdate` schema allows *simultaneous* update of `start_at`/`end_at` and `status = "cancelled"`. If a caller sends `{"start_at": "...", "status": "cancelled"}`, it is unspecified whether:
- (a) The status cancellation takes precedence and the time fields are also updated (but overlap checks skipped), or
- (b) The service raises a validation error rejecting the mixed request.

This is an ambiguous schema/service interaction. The simplest fix is to disallow combining `status` with time/room changes, or to document the precedence rule.

**Fix:** Add to the `SessionUpdate` schema documentation:  
> "If `status = 'cancelled'` is included in the patch, all other fields (`start_at`, `end_at`, `room_id`) are ignored. The service applies only the cancellation. Callers should not send time/room changes alongside a cancellation."

Alternatively, add a schema-level `model_validator` that raises if `status = 'cancelled'` is combined with other non-None fields.

---

#### M-3 — `EnrolmentUpdate` allows setting `status` to `"withdrawn"`, `"completed"`, or `"suspended"` but the `withdrawn_at` / `completed_at` fields are on the response model — there is no mention of a `completed_at`/`withdrawn_at` input or server-set timestamp for `suspended`

**Where:** M4.2 → `update_enrolment` service function.

**Problem:** The design correctly states:  
> "Sets `withdrawn_at = utcnow()` when transitioning to `withdrawn`."  
> "Sets `completed_at = utcnow()` when transitioning to `completed`."

But there is no `suspended_at` field on `enrolments`, and the design does not document whether a suspension timestamp is tracked. This is an omission: either a `suspended_at` column should exist (and be added to the data model and `EnrolmentOut`) or the design should explicitly state that suspension is not timestamp-tracked.

**Fix:** Add one of:  
(a) A `suspended_at TIMESTAMPTZ nullable` column to the `enrolments` table definition and `EnrolmentOut`, set via the service when transitioning to `suspended`; or  
(b) An explicit note: "Suspension does not have a dedicated timestamp column; use `updated_at` to infer when the status last changed."

---

#### M-4 — `GET /api/academic/enrolments` has no pagination; at scale, listing all institutional enrolments is unbounded

**Where:** M4.2 → API surface → `GET /api/academic/enrolments`.

**Problem:** `GET /api/academic/timetable` has an explicit 500-row cap with a `X-Result-Truncated` header (M7 resolution). `GET /api/academic/enrolments` (AdminOnly, institution-wide) has no equivalent limit stated. For an institution with thousands of enrolments, this endpoint will return unbounded results.

The design is inconsistent: M4.3 explicitly addresses unbounded results for timetable queries but M4.2 does not address the same risk for enrolments.

**Fix:** Apply the same treatment as timetable:  
> "`GET /api/academic/enrolments` applies `.limit(500)`. If exactly 500 results are returned, the response includes `X-Result-Truncated: true`. Pagination is deferred."  
Or explicitly document the rationale for why enrolments can be unbounded (e.g. "institutional admin use; expected row counts are small").

---

#### M-5 — `RoomOut` schema references `RoomStatus` enum but `RoomStatus` is not added to the `enums.py` additions list

**Where:** M4.3 → Schemas → `RoomOut`; Cross-Cutting Conventions → Enum strategy; M4.3 → Enum values in `app/models/enums.py`.

**Problem:** The design lists new enum values added to `app/models/enums.py` for M4.1 (`CourseStatus`, `SubjectStatus`), M4.2 (`EnrolmentStatus`), and M4.3 — but the M4.3 enum additions section only mentions `SessionStatus` and `FacultyAssignmentStatus`. `RoomStatus` is used in `RoomOut` and `Room` model but never explicitly added to the enum additions list. The design also doesn't show the full `Room` SQLAlchemy model snippet (similar to the missing `FacultyAssignment` snippet in H-4).

**Fix:** Add `RoomStatus` to the M4.3 `app/models/enums.py` additions:

```python
class RoomStatus(str, enum.Enum):
    active   = "active"
    archived = "archived"
```

Also add the `Room` SQLAlchemy model snippet (can be brief) to confirm `TimestampMixin` is applied and the UNIQUE constraint on `(institution_id, name, building)` is in `__table_args__`.

---

#### M-6 — `SessionTypeEnum` is referenced in the `ClassSession` ORM model import but never defined anywhere in the design

**Where:** M4.3 → `ClassSession` ORM model snippet.

**Problem:** The model imports:
```python
from app.models.enums import SessionStatus, SessionTypeEnum
```

But `SESSION_TYPE` is defined as a Pydantic `Literal` alias in `app/schemas/academic.py`, not as a Python enum, and `SessionTypeEnum` is never defined or mentioned as an enum to be added to `app/models/enums.py`. The column `session_type` is `VARCHAR(20)` enforced at the application layer. If `SessionTypeEnum` is intended, it must be defined. If `session_type` is a plain string with no ORM-level enum, the import is wrong.

**Fix:** Either:  
(a) Define `SessionTypeEnum` in `app/models/enums.py` as a string enum, or  
(b) Remove the `SessionTypeEnum` import from the model and use `String(20)` without an enum type for `session_type` (consistent with how `degree_level` is handled as `VARCHAR(50)` in courses).  
State the choice explicitly. Option (b) is more consistent with the existing `degree_level` VARCHAR pattern.

---

#### M-7 — `Sidebar.tsx` uses `CalendarDays` Lucide icon but the existing sidebar imports only `CalendarRange`; `BookMarked` and `DoorOpen` are unverified

**Where:** M4.3 → Frontend integration → Sidebar links.

**Problem:** The design specifies new sidebar nav links with icons:  
- `CalendarDays` (Timetable)
- `BookMarked` (Subjects, faculty)
- `DoorOpen` (Rooms, college_admin)

Verified against `frontend/src/components/Sidebar.tsx`:  
The current sidebar imports `BookOpen`, `CalendarRange`, `ClipboardList`, `Home`, `LogOut`, `X`. It does **not** import `CalendarDays`, `BookMarked`, or `DoorOpen`. The existing `UPCOMING` array uses `CalendarRange` (not `CalendarDays`) for a Planner link.

This is not automatically a blocker — Lucide icons are freely importable — but it has two implications:
1. The existing `CalendarRange` Planner "Coming soon" link is replaced by a real `CalendarDays` Timetable link; the design does not specify whether the `ClipboardList` Assignments and `CalendarRange` Planner stub links should be removed or kept.
2. The implementor cannot verify icon names without checking the installed Lucide version.

**Fix:** Add to the M4.3 frontend section:
> "The `UPCOMING` Coming-Soon stub list in `Sidebar.tsx` is removed entirely and replaced with the role-conditional real links. The existing stub icons (`CalendarRange`, `ClipboardList`) are no longer needed as sidebar imports after M4.3. Verify `CalendarDays`, `BookMarked`, and `DoorOpen` exist in the installed `lucide-react` version before coding."

---

### NIT

---

#### N-1 — `conftest.py` TABLES constant is not updated until after each module migration; the design gives intermediate states but the final string in M4.3 is the only one that matters at steady state

**Where:** M4.1/M4.2/M4.3 → conftest.py TABLES sections.

**Problem:** The design gives three intermediate TABLES strings. The final one in M4.3 is authoritative. The intermediate ones will be out of date after M4.3 is applied. The design should clarify that each intermediate string is temporary and only valid between migrations, not a final committed state.

**Fix:** Add a note: "Each TABLES string is the value used for tests in that module's iteration. The M4.3 string is the final steady-state value."

---

#### N-2 — `StrictModel` re-export in `app/schemas/auth.py` is described as "re-export for backward compat" but there are no external importers of `app.schemas.auth.StrictModel`

**Where:** Cross-Cutting Conventions → StrictModel refactor (H1).

**Problem:** The design says `auth.py` will `from app.schemas.base import StrictModel  # re-export for backward compat`. Verified: `StrictModel` is defined inline in `app/schemas/auth.py` and no other file in the repo imports it from there. There are no existing `from app.schemas.auth import StrictModel` usages. The "backward compat" comment is misleading for this codebase.

**Fix:** Remove the "backward compat" comment; replace with a standard import with no special comment, or omit the re-export entirely and just add the new import in `auth.py` for its own schemas.

---

#### N-3 — `SessionCreate` does not include `faculty_assignment_id` derivation source for `course_id`/`subject_id` inconsistency note

**Where:** M4.3 → `create_session` service function, step 2.

**Problem:** The design correctly states:  
> "2. Derive `course_id` and `subject_id` from the assignment row (not from the request body — prevents mismatch)."

But the `SessionCreate` schema does not include `course_id` or `subject_id` fields, which is correct. However, `SessionOut` **does** include `course_id` and `subject_id`. A coder implementing the create endpoint might wonder where these come from in the response. The design implies they're taken from the assignment, but this is not stated in the schema documentation.

**Fix:** Add to `SessionCreate` schema documentation:  
> "`course_id` and `subject_id` are not accepted in the request body. They are populated on the created session from the `faculty_assignment` row."

---

## Verified Assumptions

The following design claims were verified against the actual repository source:

1. **`TenantContext` shape** — `deps.py` confirms `TenantContext.institution_id`, `TenantContext.role`, `TenantContext.membership`, `TenantContext.user` are all available as stated.

2. **`require_roles` signature** — Verified: `require_roles(*roles: MembershipRole)` returns a `Callable[[TenantContext], TenantContext]`. The `AnyMember`/`AdminOnly`/`StudentOnly` dependency aliases are correctly constructible.

3. **`MembershipRole` enum values** — Verified in `app/models/enums.py`: `student`, `faculty`, `college_admin`. No `platform_admin` membership role; platform admin is a `is_platform_admin` user flag. Design correctly uses `PlatformAdmin = Annotated[Principal, Depends(require_platform_admin)]`.

4. **`MembershipStatus.active`** — Verified in `app/models/enums.py`: values are `active`, `suspended`. Design correctly validates `membership.status != active`.

5. **Transaction-scoped tenant context via `app.tenant_id`/`app.user_id`** — Verified in `app/db/session.py`: `set_config(..., is_local => true)` scopes to transaction. The `after_begin` listener re-applies on every new transaction. Design claim is accurate.

6. **`app_current_tenant()` PostgreSQL function** — Verified in `0001_identity_and_tenancy.py`: function exists, is `STABLE PARALLEL SAFE`, reads `app.tenant_id`. Design's RLS policies using `institution_id = app_current_tenant()` are correct.

7. **`ApiError(status, code, message)` signature** — Verified in `app/core/errors.py`. Design uses `ApiError(404, "code", "message")` consistently.

8. **`forbidden(code, message)` helper** — Verified: takes two positional string args. Design usage is consistent.

9. **`TimestampMixin` fields** — Verified in `app/db/base.py`: `created_at` and `updated_at` both `DateTime(timezone=True)`. `updated_at` has `onupdate=func.now()`. Design's ORM-only mutation rule is correctly motivated.

10. **Existing `Membership` model `__table_args__`** — Verified: currently only `UniqueConstraint("institution_id", "user_id", ...)` and `Index("ix_memberships_user_id", ...)`. The design correctly identifies that `UNIQUE (institution_id, id)` does not yet exist and must be added in migration 0005.

11. **`ForeignKeyConstraint` `match` and `use_alter` kwargs** — Verified against installed SQLAlchemy 2.0.58: both `match` and `use_alter` are valid `ForeignKeyConstraint` parameters.

12. **Existing migrations chain** — Verified: `0001` (base) → `0002` → `0003`. Design's `0004` with `down_revision = "0003"` is correct.

13. **`conftest.py` existing `TABLES` constant** — Verified: `"password_reset_tokens, rate_limit_buckets, refresh_tokens, auth_sessions, memberships, users, institutions"`. Design's M4.1 TABLES string adds `subjects, courses` at the front, which is correct FK order.

14. **Router registration pattern in `main.py`** — Verified: `app.include_router(router, prefix="/api")`. Design's `academic.router` with internal `prefix="/academic"` is consistent with how `auth.router` uses `prefix="/auth"`.

15. **`switch-institution` returns HTTP 200** — Verified in `app/api/auth.py`: `@router.post("/switch-institution", response_model=MeResponse)` with no explicit `status_code` → defaults to 200. ✓

---

## Unverified / Wrong Assumptions

1. **`logout` → HTTP 200 (WRONG — it is 204):** Verified in `app/api/auth.py`: `@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT, ...)`. The design's archive-convention justification uses `logout → 200` as an example, which is factually incorrect. See H-1.

2. **`memberships_select` RLS policy isolates by `institution_id` only (WRONG — it's OR-based):** Verified in `0001_identity_and_tenancy.py`: the policy uses `institution_id = app_current_tenant() OR user_id = app_current_user()`. The design's M9 claim that "RLS on memberships selects by `institution_id = app_current_tenant()`" is a simplification that omits the `OR` branch. See H-2.

3. **`SessionTypeEnum` is defined in `app/models/enums.py` (UNVERIFIED — it does not exist):** The `ClassSession` model imports `SessionTypeEnum` from `app/models/enums`, but that file currently has no such enum, and the design never defines it. See M-6.

4. **`RoomStatus` is defined in `app/models/enums.py` (UNVERIFIED — it does not exist):** The `RoomOut` schema references `RoomStatus` but the enum additions in the design for M4.3 do not list it. See M-5.

5. **`CalendarDays`, `BookMarked`, `DoorOpen` Lucide icons exist in the installed package (UNVERIFIED):** The existing `Sidebar.tsx` uses `CalendarRange`, not `CalendarDays`. The design specifies `CalendarDays` without noting this discrepancy. See M-7.

6. **`app/schemas/auth.py` has external importers of `StrictModel` (WRONG — none exist):** No file imports `StrictModel` from `app.schemas.auth`. The "backward compat" justification for the re-export is false. See N-2.
