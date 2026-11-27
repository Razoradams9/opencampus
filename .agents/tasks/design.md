# M4 Academic Batch — Technical Design

**Revision:** 3 (post-review-2)
**Date:** 2026-11-26
**Branch:** main
**Covers:** M4.1 Courses & Subjects, M4.2 Student Enrolments, M4.3 Timetable System

---

## Overview

This document describes the concrete implementation plan for the three M4 modules. Each module is a strict dependency of the next; migrations, tests, and integration verification must be completed in order before proceeding to the subsequent module.

The design follows all existing conventions: synchronous SQLAlchemy 2.0 ORM with explicit `institution_id` filters plus PostgreSQL RLS as a backstop, transaction-scoped tenant context via `app.tenant_id` / `app.user_id` settings, `StrictModel` Pydantic schemas, `ApiError` / `forbidden` / `unauthorized` helpers, and Alembic migrations starting from revision `0004`. Every new router is registered in `app/main.py` under the `/api` prefix, identical to existing routers.

The backend APIs are designed to be client-agnostic: a future OpenCampus Student app, Faculty app, or Administration app will call the same endpoints; no routing or response shaping will differ based on the caller. The frontend integration described in each module is the current single-client implementation; it does not create client-specific API contracts.

---

## Technology Stack (locked)

| Layer | Technology |
|---|---|
| Backend language | Python 3.11+ |
| Web framework | FastAPI |
| ORM | Synchronous SQLAlchemy 2.0 |
| DB driver | psycopg 3 |
| Migrations | Alembic (manual, hand-authored) |
| Database | PostgreSQL 16 |
| Auth | PyJWT + Argon2id (unchanged) |
| Frontend | React 19, TypeScript, Vite 8, Tailwind CSS 4 |
| Frontend routing | Custom history-API router (existing `lib/router.tsx`) |
| Frontend icons | Lucide (lucide-react 1.79.0, verified) |

---

## Cross-Cutting Conventions (all three modules)

### StrictModel refactor

`StrictModel` currently lives in `app/schemas/auth.py`. Before writing `app/schemas/academic.py`, it must be extracted to a new shared module so both schema files can import from the same source.

**New file: `app/schemas/base.py`**

```python
from pydantic import BaseModel, ConfigDict


class StrictModel(BaseModel):
    # Unknown fields are rejected so e.g. {"role": "college_admin"} in a
    # registration body fails validation instead of being silently ignored.
    model_config = ConfigDict(extra="forbid")
```

**Modified: `app/schemas/auth.py`** — replace the inline `StrictModel` definition with:

```python
from app.schemas.base import StrictModel
```

`app/schemas/academic.py` then imports `from app.schemas.base import StrictModel`.

### ORM-only mutation rule

All row mutations across M4 services use ORM-level `session.flush()` / `session.commit()`. Raw `UPDATE` statements are prohibited for tables that carry `updated_at`. This ensures that `TimestampMixin.updated_at`'s `onupdate=func.now()` fires correctly on every mutation. As defence-in-depth, migration 0004 adds a `BEFORE UPDATE` trigger on `courses` and `subjects`; migration 0005 on `enrolments`; migration 0006 on `rooms` and `class_sessions`. The trigger pattern:

```sql
CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
  NEW.updated_at = now();
  RETURN NEW;
END;
$$;

CREATE TRIGGER trg_<table>_updated_at
BEFORE UPDATE ON <table>
FOR EACH ROW EXECUTE FUNCTION set_updated_at();
```

The function is created once in migration 0004 and reused by all subsequent migrations.

### RLS pattern

Every new institution-owned table uses the same four-policy pattern established in `0001_identity_and_tenancy.py`:

```sql
ALTER TABLE <table> ENABLE ROW LEVEL SECURITY;
ALTER TABLE <table> FORCE ROW LEVEL SECURITY;

CREATE POLICY <table>_select ON <table> FOR SELECT
  USING (institution_id = app_current_tenant());

CREATE POLICY <table>_insert ON <table> FOR INSERT
  WITH CHECK (institution_id = app_current_tenant());

CREATE POLICY <table>_update ON <table> FOR UPDATE
  USING  (institution_id = app_current_tenant())
  WITH CHECK (institution_id = app_current_tenant());

CREATE POLICY <table>_delete ON <table> FOR DELETE
  USING (institution_id = app_current_tenant());
```

Grant:

```sql
GRANT SELECT, INSERT, UPDATE ON <table> TO <app_role>;
-- DELETE is never granted on academic tables. All removal is archiving or cancellation.
-- This prevents physical deletion even if service code contained a bug.
```

### institution_id enforcement

`institution_id` is never accepted from, or derived from, any request body field. It is always taken from `tenant.institution_id` in the service layer. The dependency chain `get_principal → get_tenant → require_roles(...)` sets the tenant context before any service call runs.

UUID references to other tenant-owned objects (such as `student_membership_id`, `course_id`, `faculty_membership_id`) are accepted from the request body but are **always re-validated against `institution_id` server-side**. The validation pattern is `SELECT … WHERE institution_id = <tenant.institution_id> AND id = <body_uuid>`. A UUID that exists in the database but belongs to a different institution returns `404`, not `403`. This ensures callers cannot infer the existence of foreign-institution records from error codes.

### Composite foreign keys

Where cross-institution data linkage must be prevented at the database level, composite FKs on `(institution_id, <other_id>)` reference `(institution_id, id)` unique constraints on the parent table. This requires unique constraints on `(institution_id, id)` for `courses`, `subjects`, `rooms`, and `memberships`.

### Migration helper

Each new migration file defines the same `_app_role()` helper used in existing migrations:

```python
def _app_role() -> str:
    role = os.getenv("OPENCAMPUS_DB_APP_ROLE", "opencampus_app")
    if not re.fullmatch(r"[a-z_][a-z0-9_]{0,62}", role):
        raise ValueError(f"Invalid OPENCAMPUS_DB_APP_ROLE: {role!r}")
    return role
```

### Archive and cancel operations

Archiving sets `status = 'archived'` and never deletes. Cancel operations set `status = 'cancelled'`. Archive and cancel endpoints use the convention `POST /api/academic/<resource>/{id}/archive` (or `/cancel`). **These endpoints return HTTP 200 with the updated resource body. No redirect, no 204.**

No DELETE is granted on any academic table (`courses`, `subjects`, `enrolments`, `rooms`, `faculty_assignments`, `class_sessions`). Cancelled and archived rows are retained as historical record indefinitely.

### Enum strategy

New Python enums are added to `app/models/enums.py`. New PostgreSQL enum types are created in the migration. Downgrade drops the type only after dropping dependent columns/tables.

### DEGREE_LEVEL type alias

To avoid invalid Python in schema snippets, a type alias is defined at module level in `app/schemas/academic.py`:

```python
from typing import Literal
DEGREE_LEVEL = Literal[
    "certificate", "diploma", "associate",
    "bachelor", "master", "doctoral", "professional"
]
```

All `CourseCreate` and `CourseUpdate` schemas reference `DEGREE_LEVEL` by name.

### conftest.py TABLES constant

Each new migration adds its table names to the `TABLES` truncation list in `tests/conftest.py`. Tables are listed in reverse FK dependency order for `TRUNCATE … CASCADE` correctness: children before parents. Each intermediate TABLES string is the value used for that module's tests only. The M4.3 string is the final steady-state value.

---

## M4.1 — Courses and Subjects

### Data model

**`courses` table**

| Column | Type | Constraints |
|---|---|---|
| `id` | `UUID` | PK, `server_default gen_random_uuid()` |
| `institution_id` | `UUID` | FK → `institutions.id` ON DELETE CASCADE, NOT NULL |
| `name` | `VARCHAR(200)` | NOT NULL |
| `code` | `VARCHAR(20)` | NOT NULL |
| `description` | `TEXT` | nullable |
| `degree_level` | `VARCHAR(50)` | NOT NULL |
| `duration_semesters` | `SMALLINT` | NOT NULL, CHECK > 0 |
| `status` | `course_status` enum | NOT NULL, default `active` |
| `created_at` | `TIMESTAMPTZ` | NOT NULL, `server_default now()` |
| `updated_at` | `TIMESTAMPTZ` | NOT NULL, `server_default now()` |

Constraints:
- `UNIQUE (institution_id, code)` — unique course code per institution
- `UNIQUE (institution_id, id)` — enables composite FK from child tables
- `CHECK (duration_semesters > 0)`

Indexes:
- `ix_courses_institution_id` on `institution_id`

`degree_level` is a `VARCHAR(50)` enforced by the `DEGREE_LEVEL` Pydantic type alias. It is not a PostgreSQL enum because degree levels may expand without a migration.

`course_status` PostgreSQL enum: `active`, `archived`.

**`subjects` table**

| Column | Type | Constraints |
|---|---|---|
| `id` | `UUID` | PK, `server_default gen_random_uuid()` |
| `institution_id` | `UUID` | NOT NULL |
| `course_id` | `UUID` | NOT NULL |
| `name` | `VARCHAR(200)` | NOT NULL |
| `code` | `VARCHAR(20)` | NOT NULL |
| `description` | `TEXT` | nullable |
| `semester` | `SMALLINT` | NOT NULL, CHECK ≥ 1 |
| `credits` | `NUMERIC(4,1)` | NOT NULL, CHECK > 0 |
| `status` | `subject_status` enum | NOT NULL, default `active` |
| `created_at` | `TIMESTAMPTZ` | NOT NULL |
| `updated_at` | `TIMESTAMPTZ` | NOT NULL |

Constraints:
- `FK (institution_id, course_id) → courses (institution_id, id) ON DELETE CASCADE` — composite FK guarantees the subject belongs to a course in the same institution
- `UNIQUE (institution_id, code)` — subject codes are unique per institution, not just per course, so a code like `CS201` unambiguously identifies a subject within a tenant
- `UNIQUE (institution_id, id)` — enables composite FK from timetable tables
- `CHECK (semester >= 1)`
- `CHECK (credits > 0)`

Indexes:
- `ix_subjects_course_id` on `course_id`
- `ix_subjects_institution_id` on `institution_id`

The semester-vs-duration validation (semester must not exceed `course.duration_semesters`) is enforced at the service layer, not via a database constraint, because it requires a cross-row lookup. It is checked on both create and patch. If a course's `duration_semesters` is later reduced below an existing subject's semester value, that subject is left in place (no cascade-invalidation); only new writes are blocked.

`subject_status` PostgreSQL enum: `active`, `archived`.

**SQLAlchemy models** — `app/models/course.py` and `app/models/subject.py`:

```python
# app/models/course.py
import uuid
from sqlalchemy import (
    CheckConstraint, Enum, ForeignKey,
    SmallInteger, String, Text, UniqueConstraint, text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base, TimestampMixin
from app.models.enums import CourseStatus


class Course(TimestampMixin, Base):
    __tablename__ = "courses"
    __table_args__ = (
        UniqueConstraint("institution_id", "code", name="uq_courses_institution_id_code"),
        UniqueConstraint("institution_id", "id",   name="uq_courses_institution_id_id"),
        CheckConstraint("duration_semesters > 0",  name="ck_courses_duration_positive"),
    )
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    institution_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("institutions.id", ondelete="CASCADE"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    code: Mapped[str] = mapped_column(String(20),  nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    degree_level: Mapped[str] = mapped_column(String(50), nullable=False)
    duration_semesters: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    status: Mapped[CourseStatus] = mapped_column(
        Enum(CourseStatus, name="course_status"), nullable=False,
        server_default=CourseStatus.active.value,
    )
    subjects: Mapped[list["Subject"]] = relationship(back_populates="course")
```

```python
# app/models/subject.py
import uuid
from sqlalchemy import (
    CheckConstraint, Enum, ForeignKeyConstraint, Numeric,
    SmallInteger, String, Text, UniqueConstraint, text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base, TimestampMixin
from app.models.enums import SubjectStatus


class Subject(TimestampMixin, Base):
    __tablename__ = "subjects"
    __table_args__ = (
        ForeignKeyConstraint(
            ["institution_id", "course_id"],
            ["courses.institution_id", "courses.id"],
            name="fk_subjects_institution_id_course_id_courses",
            ondelete="CASCADE",
        ),
        UniqueConstraint("institution_id", "code", name="uq_subjects_institution_id_code"),
        UniqueConstraint("institution_id", "id",   name="uq_subjects_institution_id_id"),
        CheckConstraint("semester >= 1",   name="ck_subjects_semester_positive"),
        CheckConstraint("credits > 0",     name="ck_subjects_credits_positive"),
    )
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    institution_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    course_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    code: Mapped[str] = mapped_column(String(20),  nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    semester: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    credits: Mapped[float] = mapped_column(Numeric(4, 1), nullable=False)
    status: Mapped[SubjectStatus] = mapped_column(
        Enum(SubjectStatus, name="subject_status"), nullable=False,
        server_default=SubjectStatus.active.value,
    )
    course: Mapped["Course"] = relationship(back_populates="subjects")
```

**New enum values in `app/models/enums.py`:**

```python
class CourseStatus(str, enum.Enum):
    active   = "active"
    archived = "archived"

class SubjectStatus(str, enum.Enum):
    active   = "active"
    archived = "archived"
```

### Alembic migration: `0004_courses_and_subjects.py`

Revision `0004`, `down_revision = "0003"`. Creates both tables, enums, indexes, the `set_updated_at()` trigger function, `updated_at` triggers on both tables, RLS policies, and grants in a single migration.

Steps in upgrade:
1. Create `course_status` and `subject_status` enum types.
2. Create `courses` table with all constraints.
3. Create `subjects` table with all constraints.
4. Create indexes.
5. Create `set_updated_at()` trigger function (once; reused in 0005 and 0006).
6. Create `trg_courses_updated_at` and `trg_subjects_updated_at` triggers.
7. Enable and force RLS on `courses` and `subjects`.
8. Create four RLS policies for each table (standard pattern).
9. `GRANT SELECT, INSERT, UPDATE ON courses, subjects TO <app_role>`. No DELETE granted.

Downgrade reverses in dependency order: drop triggers, drop tables, drop enums, drop policies, drop trigger function.

RLS policies use `institution_id = app_current_tenant()` for all four operations on both tables.

### API surface

**Router:** `app/api/academic.py` — single file for all M4 academic endpoints, registered in `main.py` as:

```python
from app.api import academic
app.include_router(academic.router, prefix="/api")
```

The router uses `prefix="/academic"` internally.

**Dependency aliases defined in `app/api/academic.py`:**

```python
from typing import Annotated
from fastapi import Depends
from app.api.deps import TenantContext, require_roles
from app.models.enums import MembershipRole

AnyMember = Annotated[TenantContext, Depends(require_roles(
    MembershipRole.student, MembershipRole.faculty, MembershipRole.college_admin
))]
AdminOnly = Annotated[TenantContext, Depends(require_roles(MembershipRole.college_admin))]
```

**M4.1 Endpoints:**

| Method | Path | Auth | Status | Description |
|---|---|---|---|---|
| `GET` | `/api/academic/courses` | AnyMember | 200 | List courses. Query: `include_archived: bool = False`. |
| `POST` | `/api/academic/courses` | AdminOnly | 201 | Create a course. |
| `GET` | `/api/academic/courses/{id}` | AnyMember | 200 | Get course by ID. |
| `PATCH` | `/api/academic/courses/{id}` | AdminOnly | 200 | Update course fields. |
| `POST` | `/api/academic/courses/{id}/archive` | AdminOnly | 200 | Archive a course. Returns updated `CourseOut`. |
| `GET` | `/api/academic/courses/{id}/subjects` | AnyMember | 200 | List subjects for a course. Query: `include_archived: bool = False`. |
| `POST` | `/api/academic/courses/{id}/subjects` | AdminOnly | 201 | Create a subject under a course. |
| `GET` | `/api/academic/subjects/{id}` | AnyMember | 200 | Get subject by ID. |
| `PATCH` | `/api/academic/subjects/{id}` | AdminOnly | 200 | Update subject fields. |
| `POST` | `/api/academic/subjects/{id}/archive` | AdminOnly | 200 | Archive a subject. Returns updated `SubjectOut`. |

**Platform admin access:** Platform admins have no M4 academic management route. They operate through `platform.py`. If a platform admin needs to manage academic records for a specific institution they must hold a `college_admin` membership there — the same mechanism used throughout.

**Pydantic schemas** (`app/schemas/academic.py`):

```python
from __future__ import annotations
import uuid
from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from app.schemas.base import StrictModel
from app.models.enums import CourseStatus, SubjectStatus

DEGREE_LEVEL = Literal[
    "certificate", "diploma", "associate",
    "bachelor", "master", "doctoral", "professional",
]


class CourseCreate(StrictModel):
    name: str = Field(min_length=2, max_length=200)
    code: str = Field(min_length=1, max_length=20, pattern=r"^[A-Za-z0-9_-]+$")
    description: str | None = Field(default=None, max_length=2000)
    degree_level: DEGREE_LEVEL
    duration_semesters: int = Field(ge=1, le=20)


class CourseUpdate(StrictModel):
    name: str | None = Field(default=None, min_length=2, max_length=200)
    description: str | None = None
    degree_level: DEGREE_LEVEL | None = None
    duration_semesters: int | None = Field(default=None, ge=1, le=20)
    # status is NOT patchable via PATCH; use the archive sub-resource


class CourseOut(BaseModel):
    id: uuid.UUID
    institution_id: uuid.UUID
    name: str
    code: str
    description: str | None
    degree_level: str
    duration_semesters: int
    status: CourseStatus
    created_at: datetime
    updated_at: datetime


class SubjectCreate(StrictModel):
    name: str = Field(min_length=2, max_length=200)
    code: str = Field(min_length=1, max_length=20, pattern=r"^[A-Za-z0-9_-]+$")
    description: str | None = Field(default=None, max_length=2000)
    semester: int = Field(ge=1)
    credits: Decimal = Field(gt=Decimal("0"), max_digits=4, decimal_places=1)
    # course_id is taken from the URL path, not the body


class SubjectUpdate(StrictModel):
    name: str | None = Field(default=None, min_length=2, max_length=200)
    description: str | None = None
    semester: int | None = Field(default=None, ge=1)
    credits: Decimal | None = Field(default=None, gt=Decimal("0"), max_digits=4, decimal_places=1)


class SubjectOut(BaseModel):
    id: uuid.UUID
    institution_id: uuid.UUID
    course_id: uuid.UUID
    name: str
    code: str
    description: str | None
    semester: int
    credits: Decimal
    status: SubjectStatus
    created_at: datetime
    updated_at: datetime
```

### Service layer (`app/services/academic.py`)

One service module for all three M4 modules' service functions, growing incrementally. All mutations use ORM `flush()` / `commit()` only — no raw `UPDATE` statements.

**`get_course(db, institution_id, course_id)`**: selects with explicit `institution_id` and `id` filter. Returns `Course` or raises `ApiError(404, "course_not_found", ...)`.

**`list_courses(db, institution_id, include_archived)`**: filters `institution_id`, optionally excludes archived.

**`create_course(db, institution_id, data)`**: validates degree_level (redundant given Pydantic but provides consistent error code `invalid_degree_level`), builds `Course` ORM object, adds to session, calls `db.flush()`, catches `IntegrityError` on the unique code constraint → `ApiError(409, "code_taken", ...)`, then `db.commit()`.

**`update_course(db, institution_id, course_id, data)`**: fetches course, applies non-null fields via ORM attribute assignment. If `duration_semesters` is reduced, queries for active subjects with `semester > new_value`; if any found, raises `ApiError(409, "duration_would_invalidate_subjects", ...)`. Calls `db.flush()` then `db.commit()`.

**`archive_course(db, institution_id, course_id)`**: fetches course, sets `course.status = CourseStatus.archived`, `db.flush()`, `db.commit()`. (M4.2 extends this with an enrolment check.)

**`get_subject(db, institution_id, subject_id)`**: explicit `institution_id` + `id` filter.

**`list_subjects_for_course(db, institution_id, course_id, include_archived)`**: validates course exists (404 if not), then queries subjects.

**`create_subject(db, institution_id, course_id, data)`**: fetches course (404 if not found, 409 if archived via `ApiError(409, "course_archived", ...)`), validates `data.semester <= course.duration_semesters` (raises `ApiError(422, "semester_exceeds_duration", ...)`), builds `Subject`, flushes, catches `IntegrityError` on unique code → `ApiError(409, "code_taken", ...)`, commits.

**`update_subject(db, institution_id, subject_id, data)`**: fetches subject and its course. If `semester` is being updated, re-validates against `course.duration_semesters`. All changes via ORM attribute assignment + flush + commit.

**`archive_subject(db, institution_id, subject_id)`**: sets `status = SubjectStatus.archived`, flush, commit. (M4.3 extends this with a faculty assignment check.)

### Error handling (M4.1)

| Operation | Failure condition | Recovery | Caller receives | Logged |
|---|---|---|---|---|
| `create_course` | Duplicate code | Recoverable | 409 `code_taken` | No |
| `create_course` | DB error | Fatal | 500 | Yes (uvicorn) |
| `update_course` | Duration reduction invalidates subjects | Recoverable | 409 `duration_would_invalidate_subjects` | No |
| `create_subject` | Semester > course duration | Recoverable | 422 `semester_exceeds_duration` | No |
| `create_subject` | Duplicate code | Recoverable | 409 `code_taken` | No |
| `create_subject` | Parent course archived | Recoverable | 409 `course_archived` | No |
| Any get/update/archive | Not found | Recoverable | 404 `course_not_found` / `subject_not_found` | No |

### Permission matrix (M4.1)

| Operation | student | faculty | college_admin | platform_admin |
|---|---|---|---|---|
| List/get courses | ✓ | ✓ | ✓ | — |
| Create/update/archive course | — | — | ✓ | — |
| List/get subjects | ✓ | ✓ | ✓ | — |
| Create/update/archive subject | — | — | ✓ | — |

Platform admins have no M4.1 access. If they need to manage academic records for a specific institution they must hold a `college_admin` membership there.

### Test plan (M4.1)

File: `tests/test_academic_courses.py`

1. `test_create_course_success` — college_admin creates a course; response matches payload; persisted in DB.
2. `test_create_course_duplicate_code` — 409 on second creation with same code in same institution.
3. `test_create_course_different_institutions_same_code` — two institutions may share a code.
4. `test_list_courses_excludes_archived_by_default` — list returns only active courses without flag.
5. `test_list_courses_includes_archived_when_flagged` — with `include_archived=true`.
6. `test_student_cannot_create_course` — 403.
7. `test_faculty_cannot_create_course` — 403.
8. `test_archive_course` — status flips to archived; can still GET it; HTTP 200 returned.
9. `test_reduce_duration_invalidates_subjects_blocked` — 409 when reduction would invalidate an existing active subject.
10. `test_create_subject_semester_exceeds_duration` — 422.
11. `test_create_subject_duplicate_code` — 409.
12. `test_archive_subject` — status flips to archived; HTTP 200 returned.
13. `test_cannot_add_subject_to_archived_course` — 409.
14. `test_rls_course_isolation` — tenant A cannot see tenant B's courses; DB query with tenant A context returns 0 rows for tenant B data.
15. `test_rls_subject_isolation` — same for subjects.
16. `test_rls_app_role_cannot_delete_courses` — verify app role has no DELETE grant on `courses` and `subjects`.
17. `test_api_course_isolation` — API call: admin of institution A cannot GET a course belonging to institution B (returns 404).

**conftest.py TABLES update after 0004** (temporary; valid until 0005 is applied; reverse FK order — subjects before courses):

```python
TABLES = "subjects, courses, password_reset_tokens, rate_limit_buckets, refresh_tokens, auth_sessions, memberships, users, institutions"
```

### Frontend integration (M4.1)

New page: `/courses` — enrolled courses list for the student.

Add route to `App.tsx`: extend the `pathname` switch in `AuthenticatedApp` to handle `/courses` → `<CoursesPage />`. New import: `import { CoursesPage } from "./pages/CoursesPage"`.

The `CoursesPage` fetches `GET /api/academic/courses` with the user's access token. While real data loads, it shows a skeleton; on empty response it shows "No courses found". The demo data in `demo.ts` continues to drive the existing dashboard widgets unmodified.

New sidebar link "Courses" using `BookOpen` Lucide icon in `Sidebar.tsx`, conditionally visible for `student` and `faculty` roles only (not `college_admin` who will get a different admin-focused view in a future phase).

API types live in `src/lib/api/academic.ts` as plain TypeScript interfaces (not in `data/types.ts` which is demo-data-scoped).

---

## M4.2 — Student Enrolments

Depends on M4.1 being fully migrated and tested.

### Data model

**Membership model analysis:** The existing `Membership` model has `id`, `institution_id`, `user_id`, `role`, `status`. There is no separate "student record" model — a student's identity within an institution is their membership row. The correct FK target is `memberships.id` constrained to membership rows with `role = 'student'`. This cannot be enforced with a simple FK; it is enforced at the service layer. The column is named `student_membership_id`.

To support composite FK from `enrolments` into `memberships` with institution-scoping, `memberships` needs a `UNIQUE (institution_id, id)` constraint. This is added in migration `0005` as an `ALTER TABLE` statement.

**Modified: `app/models/membership.py`** — add the unique constraint to `__table_args__`:

```python
__table_args__ = (
    UniqueConstraint("institution_id", "user_id", name="uq_memberships_institution_user"),
    UniqueConstraint("institution_id", "id",      name="uq_memberships_institution_id_id"),
    Index("ix_memberships_user_id", "user_id"),
)
```

**`enrolments` table**

| Column | Type | Constraints |
|---|---|---|
| `id` | `UUID` | PK |
| `institution_id` | `UUID` | NOT NULL |
| `student_membership_id` | `UUID` | NOT NULL |
| `course_id` | `UUID` | NOT NULL |
| `academic_year` | `SMALLINT` | NOT NULL |
| `academic_period` | `VARCHAR(20)` | NOT NULL |
| `status` | `enrolment_status` enum | NOT NULL, default `active` |
| `enrolled_at` | `TIMESTAMPTZ` | NOT NULL, `server_default now()` |
| `completed_at` | `TIMESTAMPTZ` | nullable |
| `withdrawn_at` | `TIMESTAMPTZ` | nullable |
| `created_at` | `TIMESTAMPTZ` | NOT NULL |
| `updated_at` | `TIMESTAMPTZ` | NOT NULL |

No `suspended_at` column. Suspension does not have a dedicated timestamp; use `updated_at` to infer when the status last changed.

Constraints:
- `FK (institution_id, student_membership_id) → memberships (institution_id, id)` — composite FK guarantees the student's membership is in the same institution
- `FK (institution_id, course_id) → courses (institution_id, id)` — composite FK guarantees the course is in the same institution
- `CHECK (academic_year >= 2000 AND academic_year <= 2100)`

Partial unique index (not a table constraint):

```sql
CREATE UNIQUE INDEX uq_enrolments_active
  ON enrolments (student_membership_id, course_id, academic_year, academic_period)
  WHERE status = 'active';
```

This allows multiple historical rows (withdrawn, completed) for the same student/course/period but only one active one.

`enrolment_status` PostgreSQL enum: `active`, `withdrawn`, `completed`, `suspended`.

Indexes:
- `ix_enrolments_student_membership_id`
- `ix_enrolments_course_id`
- `ix_enrolments_institution_id`

**SQLAlchemy model** (`app/models/enrolment.py`):

```python
import uuid
from datetime import datetime
from sqlalchemy import (
    CheckConstraint, DateTime, Enum, ForeignKeyConstraint,
    SmallInteger, String, text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func
from app.db.base import Base, TimestampMixin
from app.models.enums import EnrolmentStatus


class Enrolment(TimestampMixin, Base):
    __tablename__ = "enrolments"
    __table_args__ = (
        ForeignKeyConstraint(
            ["institution_id", "student_membership_id"],
            ["memberships.institution_id", "memberships.id"],
            name="fk_enrolments_institution_id_student_membership_id_memberships",
        ),
        ForeignKeyConstraint(
            ["institution_id", "course_id"],
            ["courses.institution_id", "courses.id"],
            name="fk_enrolments_institution_id_course_id_courses",
        ),
        CheckConstraint(
            "academic_year >= 2000 AND academic_year <= 2100",
            name="ck_enrolments_academic_year_range",
        ),
    )
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    institution_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    student_membership_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    course_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    academic_year: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    academic_period: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[EnrolmentStatus] = mapped_column(
        Enum(EnrolmentStatus, name="enrolment_status"), nullable=False,
        server_default=EnrolmentStatus.active.value,
    )
    enrolled_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    withdrawn_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
```

New enum in `enums.py`:

```python
class EnrolmentStatus(str, enum.Enum):
    active    = "active"
    withdrawn = "withdrawn"
    completed = "completed"
    suspended = "suspended"
```

### Alembic migration: `0005_student_enrolments.py`

Revision `0005`, `down_revision = "0004"`.

Steps in upgrade:
1. `ALTER TABLE memberships ADD CONSTRAINT uq_memberships_institution_id_id UNIQUE (institution_id, id)` — enables composite FK.
2. Create `enrolment_status` enum.
3. Create `enrolments` table with all constraints.
4. Create partial unique index `uq_enrolments_active`.
5. Create regular indexes.
6. Create `trg_enrolments_updated_at` trigger (reuses `set_updated_at()` function created in 0004).
7. Enable and force RLS on `enrolments`.
8. Create four RLS policies.
9. `GRANT SELECT, INSERT, UPDATE ON enrolments TO <app_role>`. No DELETE granted.

Downgrade reverses: drop index, drop triggers, drop table, drop enum, drop unique constraint from `memberships`.

### API surface

The route `/api/academic/enrolments/me` **must be registered before** `/api/academic/enrolments/{id}` in the router definition. FastAPI resolves routes in registration order; `me` would be treated as a UUID path parameter if `{id}` appears first.

```python
# In app/api/academic.py — CORRECT registration order
router.add_api_route("/enrolments/me",  get_my_enrolments,  methods=["GET"])
router.add_api_route("/enrolments/{id}", get_enrolment,      methods=["GET"])
# or equivalently using decorators, /me decorator must appear above /{id}
```

**M4.2 Endpoints:**

| Method | Path | Auth | Status | Description |
|---|---|---|---|---|
| `GET` | `/api/academic/enrolments/me` | StudentOnly | 200 | Authenticated student's own enrolments. **Registered before `/{id}`**. |
| `GET` | `/api/academic/enrolments` | AdminOnly | 200 | List enrolments for the institution. Query params: `course_id` (UUID filter), `status` filter. Max 500 rows; `X-Result-Truncated: true` header when capped. |
| `POST` | `/api/academic/enrolments` | AdminOnly | 201 | Enrol a student. |
| `GET` | `/api/academic/enrolments/{id}` | AdminOrOwnStudent | 200 | Get enrolment by ID. |
| `PATCH` | `/api/academic/enrolments/{id}` | AdminOnly | 200 | Update status (withdraw, complete, suspend). |
| `POST` | `/api/academic/enrolments/{id}/reactivate` | AdminOnly | 200 | Reactivate a withdrawn or suspended enrolment. |
| `GET` | `/api/academic/courses/{id}/enrolments` | AdminOnly (at M4.2); AdminOrAssignedFaculty (at M4.3) | 200 | Students enrolled in a course. |

**Row cap on `GET /api/academic/enrolments`:** The service applies `.limit(500)`. If exactly 500 results are returned the response includes `X-Result-Truncated: true`. Pagination is deferred. This is consistent with the same treatment applied to `GET /api/academic/timetable` in M4.3.

**`StudentOnly` dependency:**

```python
StudentOnly = Annotated[TenantContext, Depends(require_roles(MembershipRole.student))]
```

**`AdminOrOwnStudent` dependency:**

```python
def get_enrolment_or_own(
    enrolment_id: uuid.UUID,
    tenant: CurrentTenant,
    db: DbSession,
) -> tuple[TenantContext, Enrolment]:
    enrolment = service.get_enrolment(db, tenant.institution_id, enrolment_id)
    if tenant.role == MembershipRole.college_admin:
        return tenant, enrolment
    if tenant.role == MembershipRole.student:
        if enrolment.student_membership_id == tenant.membership.id:
            return tenant, enrolment
    raise forbidden("enrolment_access_denied", "You do not have access to this enrolment")
```

**`AdminOrAssignedFaculty` dependency** (defined now for M4.3 wiring):

```python
def require_admin_or_assigned_faculty(
    course_id: uuid.UUID,
    tenant: CurrentTenant,
    db: DbSession,
) -> TenantContext:
    """Used on GET /api/academic/courses/{id}/enrolments."""
    if tenant.role == MembershipRole.college_admin:
        return tenant
    if tenant.role == MembershipRole.faculty:
        # Check whether the faculty member has an active assignment for any
        # subject in this course in any academic_period.
        assignment = db.scalar(
            select(FacultyAssignment).where(
                FacultyAssignment.institution_id == tenant.institution_id,
                FacultyAssignment.course_id == course_id,
                FacultyAssignment.faculty_membership_id == tenant.membership.id,
                FacultyAssignment.status == FacultyAssignmentStatus.active,
            )
        )
        if assignment is not None:
            return tenant
    raise forbidden("insufficient_role", "You are not assigned to this course")
```

At M4.2 build time, `GET /api/academic/courses/{id}/enrolments` uses `AdminOnly`. When M4.3 is built, the dependency on that single endpoint is replaced with `Depends(require_admin_or_assigned_faculty)`. No other endpoint signatures change. The `FacultyAssignment` model and `FacultyAssignmentStatus` enum are introduced in M4.3; until then the endpoint returns 403 for all faculty.

**Reactivation design — true reactivate:**

`POST /api/academic/enrolments/{id}/reactivate` (AdminOnly, HTTP 200) sets `status = active` on the existing row. The withdrawn/completed timestamps are retained as historical record. The service checks that the target status is `withdrawn` or `suspended` before reactivating; a `completed` enrolment cannot be reactivated (raises `ApiError(422, "cannot_reactivate_completed", "Completed enrolments cannot be reactivated")`).

If the institution needs to re-enrol a student who completed a course in a new academic period, that is a new enrolment created via `POST /api/academic/enrolments` — which naturally produces a new row with a new ID.

**Status transition matrix for `update_enrolment`:**

| From ↓ / To → | active | withdrawn | completed | suspended |
|---|---|---|---|---|
| `active` | — | ✓ | ✓ | ✓ |
| `withdrawn` | use `/reactivate` | — | — | — |
| `completed` | ✗ always blocked | — | — | — |
| `suspended` | use `/reactivate` | ✓ | ✓ | — |

`PATCH` accepts only the transitions marked ✓. All others raise `ApiError(422, "invalid_status_transition", ...)`. The `/reactivate` endpoint handles `withdrawn → active` and `suspended → active`.

**Schemas** (additions to `app/schemas/academic.py`):

```python
class EnrolmentCreate(StrictModel):
    # student_membership_id and course_id are accepted from the body but are
    # always re-validated against institution_id from the token server-side.
    # A UUID that exists in the DB but belongs to a different institution
    # returns 404, not 403.
    student_membership_id: uuid.UUID
    course_id: uuid.UUID
    academic_year: int = Field(ge=2000, le=2100)
    academic_period: str = Field(min_length=1, max_length=20)


class EnrolmentUpdate(StrictModel):
    # Reactivation uses the dedicated POST .../reactivate endpoint.
    status: Literal["withdrawn", "completed", "suspended"] | None = None


class EnrolmentOut(BaseModel):
    id: uuid.UUID
    institution_id: uuid.UUID
    student_membership_id: uuid.UUID
    course_id: uuid.UUID
    academic_year: int
    academic_period: str
    status: EnrolmentStatus
    enrolled_at: datetime
    completed_at: datetime | None
    withdrawn_at: datetime | None
    created_at: datetime
    updated_at: datetime
```

### Service layer additions (M4.2)

**`create_enrolment(db, institution_id, data)`:**

Validation sequence:
1. Fetch target membership by `(institution_id, student_membership_id)` — 404 `membership_not_found` if not found (this response is returned whether the membership does not exist at all or exists in a different institution; the lookup is scoped to `institution_id` so the caller cannot distinguish the two cases). 422 `not_a_student` if `membership.role != student`. 422 `membership_suspended` if `membership.status != active`.
2. Fetch target course by `(institution_id, course_id)` — 404 `course_not_found` if not found (same 404-for-wrong-institution rule). 409 `course_archived` if archived.
3. Check for duplicate active enrolment: query the partial unique index conditions — 409 `already_enrolled` if found.
4. Build `Enrolment` ORM object, add to session, `db.flush()`.
5. Catch `IntegrityError` (race condition on the partial unique index) → 409 `already_enrolled`.
6. `db.commit()`.

**`update_enrolment(db, institution_id, enrolment_id, data)`:**

- Validates transition matrix above; raises 422 `invalid_status_transition` on invalid transitions.
- Sets `withdrawn_at = utcnow()` when transitioning to `withdrawn`.
- Sets `completed_at = utcnow()` when transitioning to `completed`.
- Suspension does not set a dedicated timestamp column; `updated_at` reflects the change.
- ORM attribute assignment + flush + commit.

**`reactivate_enrolment(db, institution_id, enrolment_id)`:**

- Fetches enrolment; 422 `cannot_reactivate_completed` if status is `completed`.
- 422 `enrolment_already_active` if status is already `active`.
- Checks for another active enrolment (same student/course/year/period) — 409 `already_enrolled` if one exists.
- Sets `status = active`, flush, commit.

**`list_my_enrolments(db, institution_id, membership_id)`:**

Returns all enrolments for `student_membership_id = membership_id`, ordered by `enrolled_at DESC`.

**`list_enrolments(db, institution_id, course_id, status)`:**

Institution-wide. Applies `.limit(500)`. Returns `(rows, truncated: bool)` where `truncated = len(rows) == 500`. The API layer sets `X-Result-Truncated: true` on the response when `truncated` is true.

**`list_enrolments_for_course(db, institution_id, course_id)`:**

Returns active enrolments for a course, ordered by `enrolled_at`.

### Archive guard added to M4.1 service (M4.2 build)

`archive_course` is extended: before setting status to archived, query for active enrolments for the course. If found, raise `ApiError(409, "active_enrolments_exist", "Cannot archive a course with active enrolments")`.

### Error handling (M4.2)

| Operation | Failure condition | Recovery | Caller receives |
|---|---|---|---|
| `create_enrolment` | Student not found in institution | Recoverable | 404 `membership_not_found` |
| `create_enrolment` | UUID exists but belongs to different institution | Recoverable | 404 `membership_not_found` / `course_not_found` |
| `create_enrolment` | Membership is not student role | Recoverable | 422 `not_a_student` |
| `create_enrolment` | Student membership suspended | Recoverable | 422 `membership_suspended` |
| `create_enrolment` | Course archived | Recoverable | 409 `course_archived` |
| `create_enrolment` | Duplicate active enrolment | Recoverable | 409 `already_enrolled` |
| `update_enrolment` | Invalid status transition | Recoverable | 422 `invalid_status_transition` |
| `reactivate_enrolment` | Completed enrolment | Recoverable | 422 `cannot_reactivate_completed` |
| `reactivate_enrolment` | Already active | Recoverable | 422 `enrolment_already_active` |
| `reactivate_enrolment` | Existing active enrolment for same period | Recoverable | 409 `already_enrolled` |
| `archive_course` | Active enrolments exist | Recoverable | 409 `active_enrolments_exist` |

### Permission matrix (M4.2)

| Operation | student | faculty | college_admin |
|---|---|---|---|
| List enrolments (institution) | — | — | ✓ |
| Create enrolment | — | — | ✓ |
| Get enrolment | own only | — | ✓ |
| Update enrolment status | — | — | ✓ |
| Reactivate enrolment | — | — | ✓ |
| List students in course | — | — (M4.3 wires) | ✓ |
| List own enrolments (`/me`) | ✓ | — | — |

Faculty gain read access to enrolled students for their assigned subjects when M4.3 wires `AdminOrAssignedFaculty` into `GET /api/academic/courses/{id}/enrolments`.

### Test plan (M4.2)

File: `tests/test_academic_enrolments.py`

1. `test_enrol_student_success`
2. `test_enrol_nonexistent_membership` — 404
3. `test_enrol_faculty_membership` — 422 `not_a_student`
4. `test_enrol_into_archived_course` — 409
5. `test_duplicate_active_enrolment` — 409
6. `test_multiple_historical_enrolments_allowed` — same student/course/period: withdraw first, create a new one (new id via `POST /api/academic/enrolments`); two rows exist
7. `test_withdraw_enrolment` — status becomes `withdrawn`; `withdrawn_at` populated
8. `test_complete_enrolment` — status becomes `completed`; `completed_at` populated
9. `test_suspend_enrolment_no_suspended_at` — status becomes `suspended`; no `suspended_at`; `updated_at` changes
10. `test_invalid_status_transition_completed_to_active_via_patch` — 422 (must use reactivate)
11. `test_reactivate_withdrawn_enrolment` — status back to `active`
12. `test_reactivate_completed_enrolment_blocked` — 422
13. `test_student_reads_own_enrolments` — `/me` returns correct data
14. `test_student_cannot_read_other_students_enrolment` — 403
15. `test_cross_institution_enrolment_blocked` — cannot enrol student_a (institution A) into course_b (institution B); service-layer institution_id from token is used, not body; 404 returned (not 403)
16. `test_enrolments_list_row_cap` — insert 501 enrolments; GET returns 500 and `X-Result-Truncated: true`
17. `test_archive_course_with_active_enrolments_blocked` — 409
18. `test_rls_enrolment_isolation` — tenant A cannot see tenant B's enrolments via DB query
19. `test_app_role_cannot_delete_enrolments`

**conftest.py TABLES update after 0005** (temporary; valid until 0006 is applied; enrolments before subjects/courses):

```python
TABLES = "enrolments, subjects, courses, password_reset_tokens, rate_limit_buckets, refresh_tokens, auth_sessions, memberships, users, institutions"
```

### Frontend integration (M4.2)

The `/courses` page (from M4.1) is extended: enrolled courses are shown with an enrolment status badge (Active, Withdrawn, Completed, Suspended) sourced from `GET /api/academic/enrolments/me`. The dashboard `AcademicProgress` demo widget continues to use demo data until real integration is confirmed in a dev session.

---

## M4.3 — Timetable System

Depends on M4.2 being fully migrated and tested.

### Data model

Three new tables: `rooms`, `faculty_assignments`, `class_sessions`.

**`rooms` table**

| Column | Type | Constraints |
|---|---|---|
| `id` | `UUID` | PK |
| `institution_id` | `UUID` | NOT NULL, FK → `institutions.id` CASCADE |
| `name` | `VARCHAR(100)` | NOT NULL |
| `building` | `VARCHAR(200)` | nullable |
| `capacity` | `SMALLINT` | nullable, `CHECK (capacity IS NULL OR capacity > 0)` |
| `status` | `room_status` enum | NOT NULL, default `active` |
| `created_at` | `TIMESTAMPTZ` | NOT NULL |
| `updated_at` | `TIMESTAMPTZ` | NOT NULL |

Constraints:
- `UNIQUE (institution_id, id)` — enables composite FK
- `UNIQUE (institution_id, name, building)` — prevents duplicate room name+building per institution

`room_status` PostgreSQL enum: `active`, `archived`.

**`faculty_assignments` table**

| Column | Type | Constraints |
|---|---|---|
| `id` | `UUID` | PK |
| `institution_id` | `UUID` | NOT NULL |
| `course_id` | `UUID` | NOT NULL |
| `subject_id` | `UUID` | NOT NULL |
| `faculty_membership_id` | `UUID` | NOT NULL |
| `academic_period` | `VARCHAR(20)` | NOT NULL |
| `status` | `faculty_assignment_status` enum | NOT NULL, default `active` |
| `created_at` | `TIMESTAMPTZ` | NOT NULL |

No `updated_at` — assignments are immutable; changing faculty for a subject means ending one assignment (`status = cancelled`) and creating a new one. This preserves history.

Constraints:
- `FK (institution_id, course_id) → courses (institution_id, id)`
- `FK (institution_id, subject_id) → subjects (institution_id, id)`
- `FK (institution_id, faculty_membership_id) → memberships (institution_id, id)` — requires `uq_memberships_institution_id_id` added in migration 0005
- Partial unique index: `CREATE UNIQUE INDEX uq_faculty_assignments_active ON faculty_assignments (institution_id, subject_id, faculty_membership_id, academic_period) WHERE status = 'active'`

The constraint that `subject.course_id == assignment.course_id` is enforced at the service layer (requires a cross-table lookup; cannot be expressed as a simple DB constraint).

A session **cannot be created against a cancelled assignment**. `create_session` raises `ApiError(409, "assignment_not_active", "Assignment is not active")` if `assignment.status != active`.

Cancelled `faculty_assignments` rows are retained indefinitely as historical record.

`faculty_assignment_status` PostgreSQL enum: `active`, `cancelled`.

**`class_sessions` table**

| Column | Type | Constraints |
|---|---|---|
| `id` | `UUID` | PK |
| `institution_id` | `UUID` | NOT NULL |
| `course_id` | `UUID` | NOT NULL |
| `subject_id` | `UUID` | NOT NULL |
| `faculty_assignment_id` | `UUID` | NOT NULL |
| `room_id` | `UUID` | nullable |
| `start_at` | `TIMESTAMPTZ` | NOT NULL |
| `end_at` | `TIMESTAMPTZ` | NOT NULL |
| `session_type` | `VARCHAR(20)` | NOT NULL |
| `status` | `session_status` enum | NOT NULL, default `scheduled` |
| `created_at` | `TIMESTAMPTZ` | NOT NULL |
| `updated_at` | `TIMESTAMPTZ` | NOT NULL |

Constraints:
- `FK (institution_id, course_id) → courses (institution_id, id)`
- `FK (institution_id, subject_id) → subjects (institution_id, id)`
- `FK faculty_assignment_id → faculty_assignments.id ON DELETE RESTRICT` (simple FK — `institution_id` is verified at service layer when fetching the assignment)
- Nullable composite FK `(institution_id, room_id) → rooms (institution_id, id)` using `MATCH SIMPLE` (see ClassSession model snippet below)
- `CHECK (end_at > start_at)`

`session_status` PostgreSQL enum: `scheduled`, `cancelled`, `completed`.

`session_type` constrained at application layer to: `Lecture`, `Tutorial`, `Lab`, `Seminar`, `Workshop`, `Other`. `VARCHAR(20)`. This is consistent with how `degree_level` is handled on courses — not a PostgreSQL enum, enforced by a Pydantic `Literal` type alias.

Indexes:
- `ix_class_sessions_start_at`
- `ix_class_sessions_faculty_assignment_id`
- `ix_class_sessions_room_id`
- `ix_class_sessions_institution_id`
- `ix_faculty_assignments_faculty_membership_id`
- `ix_faculty_assignments_subject_id`

**New enum values in `app/models/enums.py` for M4.3:**

```python
class RoomStatus(str, enum.Enum):
    active   = "active"
    archived = "archived"

class FacultyAssignmentStatus(str, enum.Enum):
    active    = "active"
    cancelled = "cancelled"

class SessionStatus(str, enum.Enum):
    scheduled = "scheduled"
    cancelled = "cancelled"
    completed = "completed"
```

**SQLAlchemy model for `Room`** (`app/models/room.py`):

```python
# app/models/room.py
import uuid
from sqlalchemy import (
    CheckConstraint, Enum, ForeignKey, SmallInteger,
    String, UniqueConstraint, text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base, TimestampMixin
from app.models.enums import RoomStatus


class Room(TimestampMixin, Base):
    __tablename__ = "rooms"
    __table_args__ = (
        UniqueConstraint("institution_id", "id",   name="uq_rooms_institution_id_id"),
        UniqueConstraint("institution_id", "name", "building",
                         name="uq_rooms_institution_id_name_building"),
        CheckConstraint(
            "capacity IS NULL OR capacity > 0",
            name="ck_rooms_capacity_positive",
        ),
    )
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    institution_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("institutions.id", ondelete="CASCADE"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    building: Mapped[str | None] = mapped_column(String(200))
    capacity: Mapped[int | None] = mapped_column(SmallInteger)
    status: Mapped[RoomStatus] = mapped_column(
        Enum(RoomStatus, name="room_status"), nullable=False,
        server_default=RoomStatus.active.value,
    )
```

**SQLAlchemy model for `FacultyAssignment`** (`app/models/faculty_assignment.py`):

`TimestampMixin` is **NOT** used — assignments are immutable; there is no `updated_at` column. `created_at` is mapped directly with `server_default=func.now()`.

```python
# app/models/faculty_assignment.py
import uuid
from datetime import datetime
from sqlalchemy import (
    DateTime, Enum, ForeignKeyConstraint, String, text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func
from app.db.base import Base   # NOT TimestampMixin
from app.models.enums import FacultyAssignmentStatus


class FacultyAssignment(Base):
    __tablename__ = "faculty_assignments"
    __table_args__ = (
        ForeignKeyConstraint(
            ["institution_id", "course_id"],
            ["courses.institution_id", "courses.id"],
            name="fk_faculty_assignments_institution_id_course_id_courses",
        ),
        ForeignKeyConstraint(
            ["institution_id", "subject_id"],
            ["subjects.institution_id", "subjects.id"],
            name="fk_faculty_assignments_institution_id_subject_id_subjects",
        ),
        ForeignKeyConstraint(
            ["institution_id", "faculty_membership_id"],
            ["memberships.institution_id", "memberships.id"],
            name="fk_faculty_assignments_institution_id_faculty_membership_id_memberships",
        ),
        # Partial unique index (uq_faculty_assignments_active) is created in
        # the migration, not here — SQLAlchemy cannot express partial indexes
        # in __table_args__ without an Index() object with a where clause.
    )
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    institution_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    course_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    subject_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    faculty_membership_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    academic_period: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[FacultyAssignmentStatus] = mapped_column(
        Enum(FacultyAssignmentStatus, name="faculty_assignment_status"), nullable=False,
        server_default=FacultyAssignmentStatus.active.value,
    )
    # created_at mapped directly — no updated_at, assignments are immutable
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    # NO updated_at — assignments are immutable; use cancel + create for changes
```

**SQLAlchemy model for `ClassSession`** (`app/models/class_session.py`):

```python
# app/models/class_session.py
import uuid
from datetime import datetime
from sqlalchemy import (
    CheckConstraint, DateTime, Enum, ForeignKey,
    ForeignKeyConstraint, String, text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base, TimestampMixin
from app.models.enums import SessionStatus


class ClassSession(TimestampMixin, Base):
    __tablename__ = "class_sessions"
    __table_args__ = (
        ForeignKeyConstraint(
            ["institution_id", "course_id"],
            ["courses.institution_id", "courses.id"],
            name="fk_class_sessions_institution_id_course_id_courses",
        ),
        ForeignKeyConstraint(
            ["institution_id", "subject_id"],
            ["subjects.institution_id", "subjects.id"],
            name="fk_class_sessions_institution_id_subject_id_subjects",
        ),
        # Nullable composite FK to rooms. MATCH SIMPLE (PostgreSQL default)
        # permits NULL on either column without voiding the whole constraint.
        # SQLAlchemy requires match="SIMPLE" to suppress its default MATCH FULL
        # behaviour, and both columns must be individually nullable=True.
        ForeignKeyConstraint(
            ["institution_id", "room_id"],
            ["rooms.institution_id", "rooms.id"],
            name="fk_class_sessions_institution_id_room_id_rooms",
            use_alter=True,     # avoids circular dependency during table creation
            match="SIMPLE",     # allows NULL room_id
        ),
        CheckConstraint("end_at > start_at", name="ck_class_sessions_end_after_start"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    institution_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    course_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    subject_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    faculty_assignment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("faculty_assignments.id", ondelete="RESTRICT"),
        nullable=False,
    )
    # room_id must be nullable=True individually for MATCH SIMPLE to allow NULL
    room_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    start_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    end_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    # session_type is VARCHAR(20), not a PG enum — consistent with degree_level
    # pattern. Enforced at application layer via SESSION_TYPE Literal alias.
    session_type: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[SessionStatus] = mapped_column(
        Enum(SessionStatus, name="session_status"), nullable=False,
        server_default=SessionStatus.scheduled.value,
    )
```

### Timezone handling

`start_at` and `end_at` are stored as `TIMESTAMPTZ` (UTC in PostgreSQL). Migration 0006 adds a `timezone` column to `institutions`.

**Modified: `app/models/institution.py`** — add:

```python
timezone: Mapped[str] = mapped_column(
    String(50), nullable=False, server_default="UTC"
)
```

**Default timezone:** `UTC`. All `start_at` and `end_at` values are stored and returned in UTC. API requests and responses always use ISO 8601 UTC timestamps (`Z` suffix). The frontend is responsible for display-layer timezone conversion using `Intl.DateTimeFormat`.

IANA timezone identifiers are stored (e.g. `"Europe/London"`, `"America/New_York"`). Frontend uses `institution.timezone` from `/api/auth/me` or a dedicated institution endpoint to display session times in local time. Backend validation requires UTC-normalised input.

### Overlap detection

Chosen approach: **`SELECT … FOR UPDATE` lock-then-check**.

The room and faculty overlap checks acquire a row lock before checking, preventing the race condition. The implementation pattern:

```python
# In create_session service function, within the same transaction:

# 1. Lock the room row for the duration of the overlap check + insert.
#    This serialises concurrent session creation for the same room.
if room_id is not None:
    db.execute(
        select(Room)
        .where(Room.institution_id == institution_id, Room.id == room_id)
        .with_for_update()
    )
    # 2. Check for overlapping sessions on this room.
    conflict = db.scalar(
        select(ClassSession.id)
        .where(
            ClassSession.room_id == room_id,
            ClassSession.institution_id == institution_id,
            ClassSession.status != SessionStatus.cancelled,
            ClassSession.start_at < end_at,
            ClassSession.end_at > start_at,
        )
        .limit(1)
    )
    if conflict:
        raise ApiError(409, "room_conflict", "Room is already booked for an overlapping time")

# 3. Lock the faculty assignment row for the faculty overlap check.
assignment = db.scalar(
    select(FacultyAssignment)
    .where(FacultyAssignment.id == faculty_assignment_id)
    .with_for_update()
)
# 4. Check for overlapping faculty sessions.
faculty_conflict = db.scalar(
    select(ClassSession.id)
    .join(FacultyAssignment, FacultyAssignment.id == ClassSession.faculty_assignment_id)
    .where(
        FacultyAssignment.faculty_membership_id == assignment.faculty_membership_id,
        ClassSession.institution_id == institution_id,
        ClassSession.status != SessionStatus.cancelled,
        ClassSession.start_at < end_at,
        ClassSession.end_at > start_at,
    )
    .limit(1)
)
if faculty_conflict:
    raise ApiError(409, "faculty_conflict", "Faculty member has an overlapping session")
```

Both checks run inside the same transaction as the insert. For `update_session`, if `start_at`, `end_at`, or `room_id` changes, the same locks are re-acquired and overlap checks re-run, excluding the current session (`AND ClassSession.id != session_id`).

### Alembic migration: `0006_timetable.py`

Revision `0006`, `down_revision = "0005"`.

Steps in upgrade:
1. `ALTER TABLE institutions ADD COLUMN timezone VARCHAR(50) NOT NULL DEFAULT 'UTC'`.
2. Create enums: `room_status`, `faculty_assignment_status`, `session_status`.
3. Create `rooms` table, indexes, `updated_at` trigger, RLS policies, grants.
4. Create `faculty_assignments` table, indexes, partial unique index, RLS policies, grants.
5. Create `class_sessions` table, indexes, `updated_at` trigger, RLS policies, grants.
6. Apply `fk_class_sessions_institution_id_room_id_rooms` (deferred via `use_alter=True`).

Grants:
- `GRANT SELECT, INSERT, UPDATE ON rooms, faculty_assignments, class_sessions TO <app_role>`
- No DELETE is granted on `rooms`, `faculty_assignments`, or `class_sessions`. Cancellation and archiving are the only removal mechanisms. Cancelled `faculty_assignments` rows and archived `rooms` are retained as historical record indefinitely.

RLS: standard four-policy pattern on `institution_id` for all three tables.

Downgrade reverses: drop tables (in dependency order), drop enums, drop `timezone` column from `institutions`.

### API surface

**M4.3 Endpoints:**

**Room management (AdminOnly):**

| Method | Path | Auth | Status | Description |
|---|---|---|---|---|
| `GET` | `/api/academic/rooms` | AdminOnly | 200 | List rooms. Query: `include_archived: bool = False`. |
| `POST` | `/api/academic/rooms` | AdminOnly | 201 | Create room. |
| `PATCH` | `/api/academic/rooms/{id}` | AdminOnly | 200 | Update room name, building, capacity. |
| `POST` | `/api/academic/rooms/{id}/archive` | AdminOnly | 200 | Archive room. Returns updated `RoomOut`. 409 if room has future scheduled sessions. |

**Faculty assignments (AdminOnly):**

| Method | Path | Auth | Status | Description |
|---|---|---|---|---|
| `GET` | `/api/academic/faculty-assignments` | AdminOnly | 200 | List assignments. Query: `subject_id`, `academic_period`. |
| `POST` | `/api/academic/faculty-assignments` | AdminOnly | 201 | Create assignment. |
| `POST` | `/api/academic/faculty-assignments/{id}/cancel` | AdminOnly | 200 | Cancel assignment. Returns updated `FacultyAssignmentOut`. 409 if assignment has future scheduled sessions. |

**Class sessions:**

| Method | Path | Auth | Status | Description |
|---|---|---|---|---|
| `GET` | `/api/academic/timetable/me` | StudentOrFaculty | 200 | Personalised timetable. **Registered before `/timetable`** to avoid route shadowing. Query: `week_start` (ISO date `YYYY-MM-DD`). |
| `GET` | `/api/academic/timetable` | AdminOnly | 200 | Institution-wide timetable. Query: `week_start`. Max 500 results. |
| `POST` | `/api/academic/timetable/sessions` | AdminOnly | 201 | Create session. |
| `PATCH` | `/api/academic/timetable/sessions/{id}` | AdminOnly | 200 | Update session. |

**`StudentOrFaculty` dependency:**

```python
StudentOrFaculty = Annotated[TenantContext, Depends(require_roles(
    MembershipRole.student, MembershipRole.faculty
))]
```

**Timetable result size limit**: `GET /api/academic/timetable` applies `.limit(500)` on the query. If the query returns exactly 500 rows, the response includes a header `X-Result-Truncated: true`. Pagination is not implemented in this iteration.

**Weekly timetable query:**

`week_start` is an ISO 8601 date string (`YYYY-MM-DD`). The backend computes `week_end = week_start + timedelta(days=7)`. Both are treated as UTC midnight for the range query (`start_at >= week_start_utc AND start_at < week_end_utc`). If `week_start` is omitted, it defaults to the Monday of the current UTC week.

Faculty timetable: filters sessions by `faculty_assignments.faculty_membership_id = tenant.membership.id`.

Student timetable: filters sessions by joining `enrolments` on `(course_id, institution_id)` where `enrolment.student_membership_id = tenant.membership.id AND enrolment.status = 'active'`.

**GET /api/academic/courses/{id}/enrolments — M4.3 wiring:**

At M4.3 build time, the dependency is replaced from `AdminOnly` to `Depends(require_admin_or_assigned_faculty)`. The endpoint body calls `service.list_enrolments_for_course(db, tenant.institution_id, course_id)` unchanged.

**Schemas** (additions to `app/schemas/academic.py`):

```python
# SESSION_TYPE Literal alias — consistent with DEGREE_LEVEL pattern.
# session_type is VARCHAR(20) in the DB, enforced here at the application layer.
SESSION_TYPE = Literal["Lecture", "Tutorial", "Lab", "Seminar", "Workshop", "Other"]


class RoomCreate(StrictModel):
    name: str = Field(min_length=1, max_length=100)
    building: str | None = Field(default=None, max_length=200)
    capacity: int | None = Field(default=None, ge=1)


class RoomUpdate(StrictModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    building: str | None = None
    capacity: int | None = Field(default=None, ge=1)


class RoomOut(BaseModel):
    id: uuid.UUID
    institution_id: uuid.UUID
    name: str
    building: str | None
    capacity: int | None
    status: RoomStatus
    created_at: datetime
    updated_at: datetime


class FacultyAssignmentCreate(StrictModel):
    # course_id, subject_id, faculty_membership_id are accepted from the body
    # and are always re-validated against institution_id from the token server-side.
    # A UUID belonging to a different institution returns 404.
    course_id: uuid.UUID
    subject_id: uuid.UUID
    faculty_membership_id: uuid.UUID
    academic_period: str = Field(min_length=1, max_length=20)


class FacultyAssignmentOut(BaseModel):
    id: uuid.UUID
    institution_id: uuid.UUID
    course_id: uuid.UUID
    subject_id: uuid.UUID
    faculty_membership_id: uuid.UUID
    academic_period: str
    status: FacultyAssignmentStatus
    created_at: datetime


# Shared base for UTC timestamp validation
class _TimestampedSessionBase(StrictModel):
    @field_validator("start_at", "end_at", mode="before")
    @classmethod
    def must_be_utc(cls, v: object) -> object:
        if isinstance(v, datetime):
            if v.tzinfo is None or v.utcoffset().total_seconds() != 0:
                raise ValueError("Timestamps must be UTC (use Z suffix)")
        return v


class SessionCreate(_TimestampedSessionBase):
    # faculty_assignment_id is the only FK accepted from the body.
    # course_id and subject_id are NOT accepted in the request body;
    # they are populated on the created session from the faculty_assignment row.
    faculty_assignment_id: uuid.UUID
    room_id: uuid.UUID | None = None
    start_at: datetime
    end_at: datetime
    session_type: SESSION_TYPE


class SessionUpdate(_TimestampedSessionBase):
    room_id: uuid.UUID | None = None
    start_at: datetime | None = None
    end_at: datetime | None = None
    # If status='cancelled' is included, all other fields (start_at, end_at,
    # room_id) are ignored and no overlap checks run. Callers should not send
    # time/room changes alongside a cancellation.
    status: Literal["cancelled"] | None = None


class SessionOut(BaseModel):
    id: uuid.UUID
    institution_id: uuid.UUID
    course_id: uuid.UUID
    subject_id: uuid.UUID
    faculty_assignment_id: uuid.UUID
    room_id: uuid.UUID | None
    start_at: datetime
    end_at: datetime
    session_type: str
    status: SessionStatus
    created_at: datetime
    updated_at: datetime


class TimetableEntry(BaseModel):
    """Enriched session for timetable display."""
    session: SessionOut
    course_name: str
    course_code: str
    subject_name: str
    subject_code: str
    room_name: str | None
    building: str | None
    faculty_full_name: str
```

### Service layer additions (M4.3)

**`create_faculty_assignment(db, institution_id, data)`:**

1. Fetch course: 404 if not found, 409 if archived.
2. Fetch subject: 404 if not found, 409 if archived. Verify `subject.course_id == data.course_id` → 422 `subject_course_mismatch`.
3. Fetch membership by `(institution_id, faculty_membership_id)`: 404 if not found. Verify `membership.role == faculty` → 422 `not_faculty`. Verify `membership.status == active` → 422 `membership_suspended`.
4. Check for duplicate active assignment → 409 `already_assigned`.
5. Build `FacultyAssignment`, flush, commit.

**`create_session(db, institution_id, data)`:**

1. Fetch faculty assignment by `institution_id + id` using `FOR UPDATE` lock: 404 if not found, 409 `assignment_not_active` if `status != active`.
2. Derive `course_id` and `subject_id` from the assignment row (not from the request body — prevents mismatch). These are stored on the session and appear in `SessionOut` but are never accepted as input.
3. Validate `data.end_at > data.start_at` — 422 `invalid_time_interval` (belt-and-suspenders; `CHECK` constraint also fires at DB level).
4. If `room_id` provided: fetch room using `FOR UPDATE` lock: 404 if not found, 409 if archived. Run room overlap check (see Overlap Detection above).
5. Run faculty overlap check using `FOR UPDATE` on assignment row (see Overlap Detection above).
6. Build `ClassSession`, flush, commit.

**`update_session(db, institution_id, session_id, data)`:**

Fetch session. If `status = cancelled` requested: set status, flush, commit; skip all overlap checks and ignore any other fields in the request (`start_at`, `end_at`, `room_id` are ignored when status is cancelled). Otherwise: if `start_at`, `end_at`, or `room_id` changes, re-acquire locks and re-run overlap checks (excluding current session `AND ClassSession.id != session_id`). Apply ORM changes, flush, commit.

**`get_my_timetable(db, institution_id, membership_id, role, week_start)`:**

The function executes a single joined ORM query. The join path for the student case:

```python
# Student timetable — ORM query sketch
stmt = (
    select(ClassSession, Course, Subject, Room, User)
    .join(FacultyAssignment, FacultyAssignment.id == ClassSession.faculty_assignment_id)
    .join(Course, and_(
        Course.institution_id == ClassSession.institution_id,
        Course.id == ClassSession.course_id,
    ))
    .join(Subject, and_(
        Subject.institution_id == ClassSession.institution_id,
        Subject.id == ClassSession.subject_id,
    ))
    .outerjoin(Room, and_(
        Room.institution_id == ClassSession.institution_id,
        Room.id == ClassSession.room_id,
    ))
    # The institution_id equality in the Membership join is the cross-institution
    # guard for this traversal. The memberships_select RLS policy uses
    # "institution_id = app_current_tenant() OR user_id = app_current_user()",
    # meaning RLS alone is NOT sufficient here; the ORM join condition
    # Membership.institution_id == FacultyAssignment.institution_id must be
    # preserved — if removed, the OR branch could leak cross-institution
    # faculty names through app_current_user().
    .join(Membership, and_(
        Membership.institution_id == FacultyAssignment.institution_id,
        Membership.id == FacultyAssignment.faculty_membership_id,
    ))
    .join(User, User.id == Membership.user_id)
    .join(Enrolment, and_(
        Enrolment.institution_id == ClassSession.institution_id,
        Enrolment.course_id == ClassSession.course_id,
        Enrolment.student_membership_id == membership_id,
        Enrolment.status == EnrolmentStatus.active,
    ))
    .where(
        ClassSession.institution_id == institution_id,
        ClassSession.start_at >= week_start_utc,
        ClassSession.start_at < week_end_utc,
        ClassSession.status != SessionStatus.cancelled,
    )
    .order_by(ClassSession.start_at)
)
rows = db.execute(stmt).all()
```

For the faculty case, replace the `Enrolment` join with a filter on `FacultyAssignment.faculty_membership_id == membership_id`.

The `faculty_full_name` field is populated from `User.full_name` via `Membership.user_id`. This is a single joined query; no separate lookup is required.

### Error handling (M4.3)

| Operation | Failure condition | Recovery | Caller receives |
|---|---|---|---|
| `create_faculty_assignment` | Subject/course mismatch | Recoverable | 422 `subject_course_mismatch` |
| `create_faculty_assignment` | Membership not faculty | Recoverable | 422 `not_faculty` |
| `create_faculty_assignment` | Duplicate active assignment | Recoverable | 409 `already_assigned` |
| `create_session` | Room overlap | Recoverable | 409 `room_conflict` |
| `create_session` | Faculty overlap | Recoverable | 409 `faculty_conflict` |
| `create_session` | end_at ≤ start_at | Recoverable | 422 `invalid_time_interval` |
| `create_session` | Assignment not active | Recoverable | 409 `assignment_not_active` |
| `archive_room` | Future sessions exist | Recoverable | 409 `future_sessions_exist` |
| `cancel_assignment` | Future sessions exist | Recoverable | 409 `future_sessions_exist` |

### Permission matrix (M4.3)

| Operation | student | faculty | college_admin |
|---|---|---|---|
| `GET /timetable` (institution-wide) | — | — | ✓ |
| `GET /timetable/me` | ✓ (own enrolments) | ✓ (own assignments) | — |
| Create/update sessions | — | — | ✓ |
| Manage rooms | — | — | ✓ |
| Manage faculty assignments | — | — | ✓ |
| List students in course | — | ✓ (assigned subjects) | ✓ |

### Test plan (M4.3)

File: `tests/test_academic_timetable.py`

1. `test_create_room` — admin creates a room.
2. `test_create_faculty_assignment_success`
3. `test_faculty_assignment_subject_course_mismatch` — 422
4. `test_faculty_assignment_not_faculty_role` — 422
5. `test_duplicate_faculty_assignment` — 409
6. `test_create_session_success`
7. `test_session_room_overlap` — 409
8. `test_session_faculty_overlap` — 409
9. `test_session_end_before_start` — 422
10. `test_cancel_session_clears_overlap` — after cancellation, same slot can be booked again
11. `test_cancel_session_ignores_time_fields` — PATCH with `{"status": "cancelled", "start_at": "..."}` applies only the cancellation
12. `test_student_timetable_me` — student sees sessions for their active enrolments, not others
13. `test_faculty_timetable_me` — faculty sees sessions for their assignments only
14. `test_student_cannot_see_other_institution_timetable`
15. `test_weekly_query_respects_boundaries` — sessions outside the week not returned
16. `test_faculty_can_list_students_in_assigned_course` — 200 after M4.3 wiring
17. `test_faculty_cannot_list_students_in_unassigned_course` — 403
18. `test_rls_session_isolation` — tenant isolation at DB level
19. `test_archive_room_with_future_sessions_blocked` — 409
20. `test_faculty_assignment_cross_institution_blocked` — attempt to create a faculty assignment where `faculty_membership_id` belongs to institution B while tenant context is institution A; expect 404 (not found in tenant). Proves service-layer institution check runs before any DB-level constraint.

**conftest.py TABLES update after 0006** (final steady-state value; class_sessions before faculty_assignments before rooms; all before enrolments):

```python
TABLES = "class_sessions, faculty_assignments, rooms, enrolments, subjects, courses, password_reset_tokens, rate_limit_buckets, refresh_tokens, auth_sessions, memberships, users, institutions"
```

### Frontend integration (M4.3)

New page: `/timetable` — weekly timetable view.

The page fetches `GET /api/academic/timetable/me?week_start=YYYY-MM-DD`. It renders a 5-column day grid (Mon–Fri) with sessions positioned by time using CSS grid. Week navigation arrows call `navigate()` with updated `week_start` query param. The existing `ScheduleItem` / `TodaySchedule` dashboard component continues to use demo data until this page is verified; once verified, the dashboard's `TodaySchedule` component is wired to filter today's sessions from the same `/timetable/me` response cached in context.

Role-conditional sidebar links — the entire `UPCOMING` Coming-Soon stub list in `Sidebar.tsx` is **removed** and replaced with real role-conditional nav links:

- Students: "Courses" (`BookOpen`), "Timetable" (`CalendarDays`)
- Faculty: "Timetable" (`CalendarDays`), "Subjects" (`BookMarked`)
- College admins: "Courses" (`BookOpen`), "Timetable" (`CalendarDays`), "Rooms" (`DoorOpen`)

After this replacement, the stub imports `CalendarRange` and `ClipboardList` are no longer needed as sidebar imports and can be removed. All three new icons — `CalendarDays`, `BookMarked`, `DoorOpen` — are confirmed present in the installed `lucide-react` 1.79.0 package (verified against `dist/lucide-react.d.ts`).

All new pages use the existing dark-slate/sage/sand palette and `AppShell` layout. No redesign of existing screens.

---

## Migration Sequence Summary

| Revision | File | Content |
|---|---|---|
| `0004` | `0004_courses_and_subjects.py` | `courses`, `subjects`, enums, `set_updated_at()` trigger function + triggers, RLS, grants |
| `0005` | `0005_student_enrolments.py` | `memberships` unique constraint, `enrolments`, enum, trigger, RLS, grants |
| `0006` | `0006_timetable.py` | `institutions.timezone`, `rooms`, `faculty_assignments`, `class_sessions`, enums, triggers, RLS, grants |

Each migration connects via `OPENCAMPUS_MIGRATION_DATABASE_URL` (owner role). The app role remains non-superuser and non-BYPASSRLS throughout.

---

## File Manifest

**New backend files:**
- `app/schemas/base.py` — `StrictModel` extracted here
- `app/models/course.py`
- `app/models/subject.py`
- `app/models/enrolment.py`
- `app/models/room.py`
- `app/models/faculty_assignment.py`
- `app/models/class_session.py`
- `app/schemas/academic.py`
- `app/services/academic.py`
- `app/api/academic.py`
- `alembic/versions/0004_courses_and_subjects.py`
- `alembic/versions/0005_student_enrolments.py`
- `alembic/versions/0006_timetable.py`
- `tests/test_academic_courses.py`
- `tests/test_academic_enrolments.py`
- `tests/test_academic_timetable.py`

**Modified backend files:**
- `app/schemas/auth.py` — replace inline `StrictModel` definition with `from app.schemas.base import StrictModel`
- `app/models/enums.py` — new enums: `CourseStatus`, `SubjectStatus`, `EnrolmentStatus`, `RoomStatus`, `FacultyAssignmentStatus`, `SessionStatus`
- `app/models/__init__.py` — new exports
- `app/models/membership.py` — add `UniqueConstraint("institution_id", "id", name="uq_memberships_institution_id_id")` to `__table_args__`
- `app/models/institution.py` — add `timezone: Mapped[str] = mapped_column(String(50), nullable=False, server_default="UTC")`
- `app/main.py` — register academic router
- `tests/conftest.py` — TABLES updated per module (see each module; M4.3 value is final)

**New frontend files:**
- `src/pages/CoursesPage.tsx`
- `src/pages/TimetablePage.tsx`
- `src/lib/api/academic.ts` — API client functions + TS interfaces

**Modified frontend files:**
- `src/App.tsx` — new routes for `/courses`, `/timetable`
- `src/components/Sidebar.tsx` — remove UPCOMING stub list; add real role-conditional nav links using `BookOpen`, `CalendarDays`, `BookMarked`, `DoorOpen`

---

## Future Multi-Client Architecture

When separate frontend applications (OpenCampus Student, Faculty, Administration) are built:

- Each will be its own Vite project with its own `VITE_API_BASE_URL`.
- They will share the same backend API endpoints defined here; no backend change is needed.
- Role-based filtering is enforced server-side; each client requests the same endpoints and receives data filtered to the authenticated user's role and institution.
- The auth session's `active_institution_id` and the membership's `role` together provide all context needed to render the correct experience in each client.
- `GET /api/academic/timetable/me` is specifically designed for this: students and faculty call the same URL and receive role-appropriate results.
- No client-identification header, parameter, or separate base path is introduced.

---

## Review Findings Response (Revision 3)

This revision addresses all 10 findings (4 HIGH, 6 MEDIUM) and 3 NITs from the second design review.

### HIGH findings

**H-1 — `logout` is HTTP 204, not 200; archive convention claim used a false analogy.**
Addressed. The archive-convention statement now reads: "Archive and cancel endpoints return HTTP 200 with the updated resource body. No redirect, no 204." The parenthetical comparison to `logout` has been removed entirely.

**H-2 — `memberships_select` RLS policy is OR-based; M9 timetable join safety claim was misleading.**
Addressed. The `get_my_timetable` ORM query sketch now contains an explicit comment block:
> "The institution_id equality in the Membership join is the cross-institution guard for this traversal. The memberships_select RLS policy uses `institution_id = app_current_tenant() OR user_id = app_current_user()`, meaning RLS alone is NOT sufficient here; the ORM join condition Membership.institution_id == FacultyAssignment.institution_id must be preserved — if removed, the OR branch could leak cross-institution faculty names."

**H-3 — `institution_id` enforcement rule was inconsistent with `EnrolmentCreate` accepting UUID references from body.**
Addressed. The cross-cutting rule now reads: "UUID references to other tenant-owned objects (such as `student_membership_id`, `course_id`) are accepted from the request body but are always re-validated against `institution_id` server-side. A UUID that exists in the database but belongs to a different institution returns 404, not 403." The `EnrolmentCreate` schema now has a comment explaining this. The error table in M4.2 now includes an explicit row for the cross-institution-UUID-reference case (404).

**H-4 — `FacultyAssignment` SQLAlchemy ORM model snippet was entirely missing.**
Addressed. Full `FacultyAssignment` ORM model snippet added, including all three `ForeignKeyConstraint` entries in `__table_args__`, explicit `created_at` column using `server_default=func.now()`, and an explicit comment that `TimestampMixin` is NOT used. A note is included that the partial unique index is created in the migration, not in `__table_args__`.

### MEDIUM findings

**M-1 — DELETE withheld from M4.3 tables not explicitly documented; unbounded cancelled-assignment accumulation unaddressed.**
Addressed. The archive-operations convention now explicitly states no DELETE is granted on any M4 academic table. The M4.3 migration grants section states: "No DELETE is granted on `rooms`, `faculty_assignments`, or `class_sessions`. Cancelled and archived rows are retained as historical record indefinitely."

**M-2 — `SessionUpdate` allowed mixing `status=cancelled` with time/room fields; precedence was unspecified.**
Addressed. The `SessionUpdate` schema now has an inline comment: "If `status='cancelled'` is included, all other fields (`start_at`, `end_at`, `room_id`) are ignored and no overlap checks run." The `update_session` service description makes this explicit. A new test `test_cancel_session_ignores_time_fields` (test #11) verifies this behaviour.

**M-3 — No `suspended_at` column or explicit note that suspension has no timestamp.**
Addressed. The `enrolments` table definition now includes: "No `suspended_at` column. Suspension does not have a dedicated timestamp; use `updated_at` to infer when the status last changed." The `update_enrolment` service description now states: "Suspension does not set a dedicated timestamp column; `updated_at` reflects the change." A new test `test_suspend_enrolment_no_suspended_at` (test #9) verifies the absence.

**M-4 — `GET /api/academic/enrolments` had no row cap; inconsistent with M4.3 timetable limit.**
Addressed. The endpoint now applies `.limit(500)` with `X-Result-Truncated: true` header on truncation, identical to the timetable. The endpoint table documents this. A new service function signature `list_enrolments` returns `(rows, truncated: bool)`. A new test `test_enrolments_list_row_cap` (test #16) verifies this.

**M-5 — `RoomStatus` enum was used but never defined; `Room` ORM model missing.**
Addressed. `RoomStatus(str, enum.Enum)` with `active`/`archived` values is added to the M4.3 enum additions list. A full `Room` SQLAlchemy ORM model snippet is added, confirming `TimestampMixin` use and the `UNIQUE(institution_id, name, building)` constraint in `__table_args__`.

**M-6 — `SessionTypeEnum` was imported in `ClassSession` model but never defined.**
Addressed. The `ClassSession` ORM model now imports only `SessionStatus` from `app.models.enums`. The `SessionTypeEnum` import is removed. `session_type` is mapped as `String(20)` with no ORM-level enum type, consistent with the `degree_level` VARCHAR pattern used in `Course`. The schema-level `SESSION_TYPE` Literal alias enforces the allowed values at the application layer.

### NIT findings

**N-1 — Intermediate TABLES strings are transient; design should note only the M4.3 string is the final steady-state.**
Addressed. Each TABLES update section now has a note marking the string as temporary. The M4.3 section says "final steady-state value" and the Cross-Cutting Conventions section states: "Each intermediate TABLES string is the value used for that module's tests only. The M4.3 string is the final steady-state value."

**N-2 — `StrictModel` re-export "backward compat" comment was misleading.**
Addressed. The comment has been removed. The modified `app/schemas/auth.py` section now simply shows `from app.schemas.base import StrictModel` with no special comment.

**N-3 — `SessionCreate` omitted a note that `course_id`/`subject_id` in `SessionOut` are derived from the assignment, not from request input.**
Addressed. The `SessionCreate` schema has an inline comment: "`course_id` and `subject_id` are NOT accepted in the request body; they are populated on the created session from the `faculty_assignment` row." This is also stated in the `create_session` service description step 2.
