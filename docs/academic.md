# Academic platform (M4): courses, enrolments, timetable

M4 adds institution-scoped academic records behind `/api/academic`, built in
three dependent modules, each migrated and tested before the next:

| Module | Migration | Tables |
| ------ | --------- | ------ |
| M4.1 Courses and subjects | `0004_courses_and_subjects` | `courses`, `subjects` |
| M4.2 Student enrolments | `0005_student_enrolments` | `enrolments` (+ `memberships (institution_id, id)` key) |
| M4.3 Timetable | `0006_timetable` | `rooms`, `faculty_assignments`, `class_sessions` (+ `institutions.timezone`, `btree_gist`) |

## One platform, several clients

OpenCampus will ship separate **Student**, **Faculty** and **Administration**
apps. All of them use the same API, identity, database and authorisation
rules:

- Authorisation depends **only** on the caller's membership in the session's
  active institution (role + status, read from the database) and on explicit
  grants such as faculty assignments. No endpoint knows or cares which app
  is calling; there is no `client` parameter or header.
- A capability the admin app will need (create a course, enrol a student,
  schedule a session) exists today as an API endpoint, guarded by the
  `college_admin` role. M5's admin UI will only add screens on top.
- "Me" endpoints (`/enrolments/me`, `/faculty-assignments/me`,
  `/timetable/me`) give every client a personal view without having to know
  membership ids.

```
 Student app ─┐
 Faculty app ─┼─▶ /api (FastAPI) ─▶ deps: principal → tenant → role ─▶ services ─▶ PostgreSQL (RLS)
 Admin app  ──┘
```

The current web app is still one React application; it shows role-specific
pages (Academics, Timetable) as integration points.

## Data model

All tables: UUID primary keys, `institution_id NOT NULL`, `created_at`/`updated_at`.

```
institutions ─┬─ courses ──────── subjects
 (timezone)   │     │                │ (institution_id, course_id, id)
              │     │                ▼
              ├─ memberships ── faculty_assignments ── class_sessions ── rooms
              │     │     (faculty)     │ (institution_id, id, faculty, course, subject)
              │     ▼
              └─ enrolments (student membership, course, year, period)
```

**courses** — `code` (upper-case, `^[A-Z0-9][A-Z0-9._-]{0,31}$`) unique per
institution; `degree_level` enum; `duration_semesters` 1–20;
`status active|archived`.

**subjects** — belongs to one course via composite FK
`(institution_id, course_id) → courses(institution_id, id)`; `code` unique
per course (two courses may reuse a code); `semester ≥ 1` and
`≤ course.duration_semesters` (service-checked under a row lock on the
course; a course cannot shrink below its subjects); `credits numeric(4,1) > 0`.

**enrolments** — student by **membership** (identity is never copied), FK
`(institution_id, student_membership_id) → memberships`; course FK likewise.
`academic_year` `YYYY-YY` (consecutive years), `academic_period` free text
(e.g. "Semester 1"). Status `active|suspended|withdrawn|completed`; partial
unique index allows one *open* (active/suspended) enrolment per student,
course, year and period. `completed_at`/`withdrawn_at` are set by the server
and DB checks require them to agree with `status`.

**rooms** — `name` unique per `(institution, building)`, optional capacity.

**faculty_assignments** — makes one faculty membership responsible for a
subject for a year and period. FK `(institution_id, course_id, subject_id) →
subjects(institution_id, course_id, id)`: the course/subject pair cannot be
inconsistent. One active assignment per subject, faculty, year and period.
Status `active|ended`.

**class_sessions** — individually scheduled classes (`start_at`, `end_at`,
`timestamptz`), no recurrence engine. `faculty_membership_id`, `course_id`
and `subject_id` are copied from the assignment and pinned by a composite FK
to it, so they can never disagree. Checks: `end_at > start_at`, max 12 h.
Status `scheduled|cancelled`.

### Overlap detection

Two GiST **exclusion constraints** on scheduled sessions:

- `ex_class_sessions_room_overlap`: same institution + room, overlapping `[start, end)`.
- `ex_class_sessions_faculty_overlap`: same institution + faculty membership, overlapping.

Intervals are half-open, so back-to-back sessions are allowed. Because the
database enforces this atomically, two concurrent requests cannot both book
the same slot (a check-then-insert in Python could). Violations map to
`409 room_conflict` / `409 faculty_conflict`. Cancelled sessions free the slot.

### Time zones

- Timestamps are stored as `timestamptz` and returned in UTC (`…Z`).
- Input must include an offset (`2027-01-04T09:00:00+05:30`); naive times are 422.
- `institutions.timezone` (IANA name, **default `UTC`**, set by a platform
  admin via `PATCH /api/platform/institutions/{slug}`) defines week
  boundaries: a week is Monday 00:00 to the next Monday 00:00 in that zone,
  computed from wall-clock dates (DST weeks are 167/169 h). The timetable
  response reports the zone; the UI formats times in it.
- `tzdata` is a dependency: Windows has no system timezone database.

### Deletion

No academic table grants `DELETE` to the runtime role, all FKs are
`ON DELETE RESTRICT`, and RLS defines no delete policy. Removal is
`archive` (courses, subjects, rooms), `end` (assignments), `cancel`
(sessions) or a status change (enrolments).

## API

All under `/api/academic`, all require a signed-in member of the active
institution. Errors use the standard `{"detail", "code"}` body. Lists accept
`limit` (1–500, default 100) and `offset` where noted.

### Courses and subjects (M4.1)

| Method | Path | Access |
| ------ | ---- | ------ |
| GET | `/courses?status=&limit=&offset=` | any member (non-admins: active only) |
| POST | `/courses` | college_admin |
| GET | `/courses/{id}` | any member (archived → 404 for non-admins) |
| PATCH | `/courses/{id}` | college_admin |
| POST | `/courses/{id}/archive`, `/courses/{id}/restore` | college_admin |
| GET | `/courses/{id}/subjects?status=` | any member |
| POST | `/courses/{id}/subjects` | college_admin |
| GET | `/subjects/{id}` | any member |
| PATCH | `/subjects/{id}` | college_admin |
| POST | `/subjects/{id}/archive`, `/subjects/{id}/restore` | college_admin |

Codes: `course_code_taken`, `subject_code_taken`, `semester_out_of_range`,
`duration_below_subjects`, `course_archived`.

### Enrolments (M4.2)

| Method | Path | Access |
| ------ | ---- | ------ |
| GET | `/enrolments?course_id=&student_membership_id=&status=&academic_year=` | admin: all · student: own · faculty: assigned |
| POST | `/enrolments` | college_admin |
| GET | `/enrolments/me?status=` | caller's own enrolments ("my courses") |
| GET | `/enrolments/{id}` | as list scope (otherwise 404) |
| PATCH | `/enrolments/{id}` `{"status"}` | college_admin |
| GET | `/courses/{id}/enrolments?status=` | admin · faculty with an active assignment in the course |

Transitions: active → suspended/withdrawn/completed; suspended →
active/withdrawn; withdrawn and completed are final. Codes:
`not_an_active_student`, `enrolment_exists`, `invalid_status_transition`,
`course_archived`, `not_assigned`.

### Timetable (M4.3)

| Method | Path | Access |
| ------ | ---- | ------ |
| GET | `/rooms?status=`, `/rooms/{id}` | any member (non-admins: active only) |
| POST | `/rooms` · PATCH `/rooms/{id}` · POST `/rooms/{id}/archive`, `/restore` | college_admin |
| GET | `/faculty-assignments?course_id=&subject_id=&faculty_membership_id=&status=&academic_year=` | admin: all · faculty: own · student: 403 |
| POST | `/faculty-assignments` `{subject_id, faculty_membership_id, academic_year, academic_period}` | college_admin |
| GET | `/faculty-assignments/me`, `/faculty-assignments/{id}` | faculty own / admin |
| POST | `/faculty-assignments/{id}/end` | college_admin |
| GET | `/timetable?week=YYYY-MM-DD&course_id=&subject_id=&room_id=&faculty_membership_id=&include_cancelled=` | college_admin |
| GET | `/timetable/me?week=&include_cancelled=` | any member: sessions taught or attended |
| POST | `/timetable/sessions` `{faculty_assignment_id, room_id?, start_at, end_at}` | college_admin |
| GET | `/timetable/sessions/{id}` | admin · the teacher · enrolled students |
| PATCH | `/timetable/sessions/{id}` `{faculty_assignment_id?, room_id?, start_at?, end_at?}` | college_admin |
| POST | `/timetable/sessions/{id}/cancel` | college_admin |

`week` is any date in the wanted week (default: today in the institution's
zone). Codes: `room_conflict`, `faculty_conflict`, `invalid_time_range`,
`assignment_ended`, `assignment_exists`, `not_an_active_faculty`,
`subject_archived`, `room_archived`, `room_has_sessions`,
`assignment_has_sessions`, `session_cancelled`.

## Permission matrix

| Capability | Student | Faculty | College admin | Platform admin (no membership) |
| ---------- | ------- | ------- | ------------- | ------------------------------ |
| Read active courses/subjects/rooms | ✓ | ✓ | ✓ (incl. archived) | — |
| Create/update/archive courses, subjects, rooms | — | — | ✓ | — |
| Read enrolments | own | matching their active assignments (course + year + period) | all | — |
| Create/change enrolments | — (no self-enrolment) | — | ✓ | — |
| Course roster | — | if assigned in course (filtered as above) | ✓ | — |
| Read assignments | — | own | all | — |
| Manage assignments, sessions | — | — | ✓ | — |
| Personal timetable (`/timetable/me`) | active enrolments | own sessions | (sessions they teach: none) | — |
| Institution timetable | — | — | ✓ | — |
| Set institution timezone | — | — | — | ✓ |

Platform admins act on academic data only through a membership; their
platform role grants no academic access (`403 tenant_required` without one).
Faculty contact details are not exposed to students (`TeacherRef` has no email).

## Visibility rules in detail

- **Student → session:** an active enrolment with the session's course whose
  `academic_year` and `academic_period` equal the session's assignment's.
- **Faculty → enrolment:** an active assignment of theirs with the
  enrolment's course, year and period. Ending the assignment removes access.

## Known limitations

- No recurrence: weekly patterns are created as individual sessions (the
  `seed-academic-demo` CLI shows how). A bulk/recurring endpoint is future work.
- `academic_period` is free text; enrolments and assignments must use the
  same label to match. A period catalogue would remove that risk.
- Student visibility is per course + period, not per semester: a student
  sees every subject of their course taught in their period.
- Changing a member's role (e.g. student → faculty) does not close their
  enrolments or assignments; new ones re-check role and status.
- RLS isolates tenants; role/ownership rules (student-own, faculty-assigned)
  are enforced in the service layer, not in RLS.
- No audit trail of who changed academic records.
- Room capacity is informational (not compared with enrolment counts).
