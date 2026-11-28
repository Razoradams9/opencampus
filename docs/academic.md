# Academic platform (M4): courses, enrolments, timetable

M4 adds institution-scoped academic records behind `/api/academic`, built in
three dependent modules, each migrated and tested before the next:

| Module | Migration | Tables |
| ------ | --------- | ------ |
| M4.1 Courses and subjects | `0004_courses_and_subjects` | `courses`, `subjects` |
| M4.2 Student enrolments | `0005_student_enrolments` | `enrolments` (+ `memberships (institution_id, id)` key) |
| M4.3 Timetable | `0006_timetable` | `rooms`, `faculty_assignments`, `class_sessions` (+ `institutions.timezone`, `btree_gist`) |
| M4.4 Learning resources | `0007_learning_resources` | `learning_resources` (+ shared `publication_status` enum) |
| M4.5 Assignments | `0008_assignments_and_submissions` | `assignments`, `submissions`, `submission_grades` |
| M4.6 Announcements | `0009_announcements` | `announcements` |

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

## Authored content (M4.4–M4.6)

All three modules share one access model (`services/academic/access.py`),
read from the database on every request:

- **Student grant:** an *active* enrolment in the course that owns the subject.
- **Faculty grant:** an *active* faculty assignment for the subject (any period).
- **College admin:** everything in the institution.
- **Platform admin:** nothing without a membership.

They also share `publication_status` (`draft → published → archived`,
`draft → archived`). `published_at` records the first publication and is
kept when archived. Archived rows are read-only and never deleted.

### File storage

There is **no file storage provider**. `services/storage.py` defines the
interface (`FileStorage`, `get_file_storage() → None`). Columns named
`storage_key` are reserved; the API never accepts or returns them and reports
`file_available: false`. Files are referenced by external `http(s)` URL until
a provider exists. Upload endpoints were deliberately not built.

### M4.4 Learning resources

`learning_resources`: subject (+ course, via the composite subject FK), author
membership, `title`, `description`, `resource_type`
(`pdf|document|presentation|video|link|note`), optional `topic`, `body`
(notes), `external_url`, `storage_key`, status. Check: a note has text and no
URL; every other type has a URL (or, later, a storage key). URLs must be
`http(s)` with a host; `javascript:`, `data:`, `file:`, `ftp:` are rejected.

| Method | Path | Access |
| ------ | ---- | ------ |
| GET | `/subjects/{id}/resources?status=` | managers: all · enrolled students: published |
| POST | `/subjects/{id}/resources` | admin · faculty teaching the subject |
| GET | `/resources/me?subject_id=` | published, from the caller's active enrolments |
| GET | `/resources/managed?subject_id=&status=` | faculty (subjects taught) · admin (all) |
| GET | `/resources/{id}` | as above, otherwise 404 |
| PATCH | `/resources/{id}` | managers; drafts and published; content re-validated on the merged result |
| POST | `/resources/{id}/publish`, `/archive` | managers |

### M4.5 Assignments and submissions

`assignments`: subject, author, `title`, `instructions`, `reference_url`,
`available_from`, `due_at` (> available_from), `late_policy`
(`reject | accept | accept_until` + `late_cutoff_at`), `max_marks` (0–1000],
status.

`submissions` (one row per **attempt**, numbered per student) and
`submission_grades` (one row per **grading event**; newest is current) are
**append-only**: the app role has `SELECT, INSERT` only. Resubmitting or
regrading adds rows; nothing is overwritten, even by a faulty service.

Late policy is applied by the server at submission time:

| Window (server clock) | `reject` | `accept` | `accept_until` |
| --------------------- | -------- | -------- | -------------- |
| before `available_from` | 409 `assignment_not_open` | same | same |
| ≤ `due_at` | on time | on time | on time |
| after `due_at` | 409 `deadline_passed` | accepted, `is_late` | accepted, `is_late` until cut-off, then 409 |

`is_late` is stored on the submission, so later deadline edits don't rewrite
history. Marks must be ≤ `max_marks` (422 `marks_exceed_maximum`), and
`max_marks` cannot drop below an awarded mark (409).

| Method | Path | Access |
| ------ | ---- | ------ |
| GET | `/assignments/me` | student: published, available, enrolled (+ archived ones they submitted to), with `me` progress |
| GET | `/assignments/managed?subject_id=&status=` | faculty / admin, with submitted/graded counts |
| GET | `/subjects/{id}/assignments` | managers · enrolled students |
| POST | `/subjects/{id}/assignments` · PATCH `/assignments/{id}` · POST `/{id}/publish`, `/archive` | managers |
| GET | `/assignments/{id}` | visible as above |
| POST | `/assignments/{id}/submissions` `{body}` | enrolled student, window open/late |
| GET | `/assignments/{id}/submissions/me` | the caller's own attempts |
| GET | `/assignments/{id}/submissions?latest_only=` | managers |
| GET | `/submissions/{id}` | owner · managers (another student's: 404) |
| POST | `/submissions/{id}/grades` `{marks_awarded, feedback}` | managers |

### M4.6 Announcements

`announcements`: author, `title`, `body`, `priority` (`normal|important|urgent`),
`audience`, optional `course_id` / `subject_id`, status, `published_at`,
`expires_at`. A check ties the audience to its target columns; composite FKs
keep targets in the institution and the (course, subject) pair consistent.

| Audience | Students who see it | Faculty who see it |
| -------- | ------------------- | ------------------ |
| `institution` | all | all |
| `course` | actively enrolled in the course | teaching any subject in the course |
| `subject` | enrolled in the subject's course | teaching the subject |
| `subject_students` | enrolled in the subject's course | — (authors reach it via *managed*) |

Admins see every published announcement. Feeds show only published,
already-published, unexpired rows (`include_expired=true` adds expired ones,
flagged `expired`). Faculty may target only `subject`/`subject_students` of
subjects they teach. The audience is re-validated on every update and again
at publish, so editing parameters cannot widen it. Only drafts are editable.

| Method | Path | Access |
| ------ | ---- | ------ |
| GET | `/announcements?include_expired=` | feed for the caller |
| POST | `/announcements` | faculty (own subjects) · admin (any audience) |
| GET | `/announcements/managed?status=` | faculty (subjects taught) · admin (all) |
| GET | `/announcements/{id}` | feed-visible or manageable |
| PATCH | `/announcements/{id}` | managers, drafts only |
| POST | `/announcements/{id}/publish`, `/archive` | managers |

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
- No file storage: resources, briefs and submissions are text or external links.
- Enrolment is per course, so "students of a subject" means students of the
  course that owns it (all semesters of that course).
- Assignment times are entered in the browser's timezone (timetable weeks use
  the institution's).
- No notifications (email/push) for new announcements, assignments or grades.
- Students may resubmit while the window is open; there is no attempt limit.
