import { ChevronDown, GraduationCap } from "lucide-react";
import { useState } from "react";
import { Empty, LoadError, Loading } from "../components/ui/DataState";
import { SectionHeading } from "../components/ui/SectionHeading";
import { SubjectMark } from "../components/ui/SubjectMark";
import { academicApi } from "../lib/academic/api";
import { toneFor } from "../lib/academic/format";
import { DEGREE_LABEL, type Course, type Enrolment, type EnrolmentStatus, type FacultyAssignment } from "../lib/academic/types";
import type { ActiveInstitution } from "../lib/auth/types";
import { useApi } from "../lib/useApi";

const STATUS_LABEL: Record<EnrolmentStatus, string> = {
  active: "Enrolled",
  suspended: "Suspended",
  withdrawn: "Withdrawn",
  completed: "Completed",
};

const plural = (n: number, word: string) => `${n} ${word}${n === 1 ? "" : "s"}`;

/** Subjects of one course, grouped by semester. Loaded on demand. */
function CourseSubjects({ courseId }: { courseId: string }) {
  const subjects = useApi((signal) => academicApi.subjects(courseId, signal), [courseId]);
  if (subjects.status === "loading") return <Loading label="Loading subjects…" />;
  if (subjects.status === "error") return <LoadError error={subjects.error} onRetry={subjects.reload} />;
  if (subjects.data.length === 0) return <Empty title="No subjects published yet" />;

  const bySemester = new Map<number, typeof subjects.data>();
  for (const s of subjects.data) bySemester.set(s.semester, [...(bySemester.get(s.semester) ?? []), s]);

  return (
    <div className="grid gap-4 px-5 pb-5 sm:grid-cols-2 sm:px-6 xl:grid-cols-3">
      {[...bySemester].map(([semester, list]) => (
        <div key={semester}>
          <p className="oc-eyebrow mb-2">Semester {semester}</p>
          <ul className="space-y-1.5">
            {list.map((s) => (
              <li key={s.id} className="flex items-start gap-2.5 rounded-lg bg-sunken/70 px-3 py-2">
                <SubjectMark tone={toneFor(s.code)} className="mt-1 size-3" />
                <div className="min-w-0 flex-1">
                  <p className="text-sm font-medium">{s.name}</p>
                  <p className="font-mono text-[0.6875rem] text-ink-subtle">
                    {s.code} · {s.credits} credits
                  </p>
                </div>
              </li>
            ))}
          </ul>
        </div>
      ))}
    </div>
  );
}

function CourseRow({ course, meta, badge }: { course: Pick<Course, "id" | "code" | "name">; meta: string; badge?: string }) {
  const [open, setOpen] = useState(false);
  const panelId = `course-${course.id}`;
  return (
    <li className="border-b border-line last:border-b-0">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        aria-controls={panelId}
        className="flex w-full items-center gap-3 px-5 py-4 text-left transition-colors hover:bg-sunken/60 sm:px-6"
      >
        <span className="grid size-10 shrink-0 place-items-center rounded-xl bg-accent-soft font-mono text-[0.625rem] font-semibold text-accent">
          {course.code.split(/[-._]/)[0].slice(0, 4)}
        </span>
        <span className="min-w-0 flex-1">
          <span className="block truncate font-display text-lg leading-tight font-medium">{course.name}</span>
          <span className="block truncate font-mono text-xs text-ink-subtle">
            {course.code} · {meta}
          </span>
        </span>
        {badge && <span className="shrink-0 rounded-full bg-success-soft px-2 py-0.5 text-[0.6875rem] font-medium text-success">{badge}</span>}
        <ChevronDown className={`size-4 shrink-0 text-ink-subtle transition-transform duration-200 ${open ? "rotate-180" : ""}`} aria-hidden="true" />
      </button>
      {open && (
        <div id={panelId} className="oc-reveal">
          <CourseSubjects courseId={course.id} />
        </div>
      )}
    </li>
  );
}

function MyCourses() {
  const enrolments = useApi((signal) => academicApi.myEnrolments(signal), []);
  return (
    <section aria-labelledby="my-courses-title">
      <SectionHeading
        id="my-courses-title"
        title="My courses"
        accent="var(--oc-subject-cobalt)"
        meta={enrolments.status === "ready" ? `${enrolments.data.filter((e) => e.status === "active").length} active` : undefined}
      />
      <div className="oc-panel">
        {enrolments.status === "loading" && <Loading label="Loading your enrolments…" />}
        {enrolments.status === "error" && <LoadError error={enrolments.error} onRetry={enrolments.reload} />}
        {enrolments.status === "ready" &&
          (enrolments.data.length === 0 ? (
            <Empty title="You are not enrolled in a course yet">Your college's administrators manage enrolments.</Empty>
          ) : (
            <ul>
              {enrolments.data.map((e: Enrolment) => (
                <CourseRow
                  key={e.id}
                  course={e.course}
                  meta={`${e.academic_year} · ${e.academic_period}`}
                  badge={e.status === "active" ? STATUS_LABEL[e.status] : undefined}
                />
              ))}
            </ul>
          ))}
        {enrolments.status === "ready" && enrolments.data.some((e) => e.status !== "active") && (
          <p className="border-t border-line px-5 py-3 text-xs text-ink-subtle sm:px-6">
            History:{" "}
            {enrolments.data
              .filter((e) => e.status !== "active")
              .map((e) => `${e.course.code} ${e.academic_year} (${STATUS_LABEL[e.status].toLowerCase()})`)
              .join(", ")}
          </p>
        )}
      </div>
    </section>
  );
}

function Teaching() {
  const assignments = useApi((signal) => academicApi.myAssignments(signal), []);
  return (
    <section aria-labelledby="teaching-title">
      <SectionHeading
        id="teaching-title"
        title="Teaching"
        accent="var(--oc-subject-teal)"
        meta={assignments.status === "ready" ? plural(assignments.data.length, "subject") : undefined}
      />
      <div className="oc-panel">
        {assignments.status === "loading" && <Loading label="Loading your assignments…" />}
        {assignments.status === "error" && <LoadError error={assignments.error} onRetry={assignments.reload} />}
        {assignments.status === "ready" &&
          (assignments.data.length === 0 ? (
            <Empty title="No teaching assignments">Your college's administrators assign subjects to faculty.</Empty>
          ) : (
            <ul className="divide-y divide-line">
              {assignments.data.map((a: FacultyAssignment) => (
                <li key={a.id} className="flex gap-3 bg-surface px-5 py-4 sm:px-6">
                  <SubjectMark tone={toneFor(a.subject.code)} className="mt-1.5 size-3.5" />
                  <div className="min-w-0">
                    <p className="font-display text-lg leading-tight font-medium">{a.subject.name}</p>
                    <p className="mt-0.5 font-mono text-xs text-ink-subtle">
                      {a.subject.code} · {a.course.code} · Sem {a.subject.semester} · {a.subject.credits} cr
                    </p>
                    <p className="mt-1 text-xs text-ink-muted">
                      {a.academic_year} · {a.academic_period}
                    </p>
                  </div>
                </li>
              ))}
            </ul>
          ))}
      </div>
    </section>
  );
}

function Catalogue() {
  const courses = useApi((signal) => academicApi.courses(signal), []);
  return (
    <section aria-labelledby="catalogue-title">
      <SectionHeading
        id="catalogue-title"
        title="Course catalogue"
        accent="var(--oc-subject-violet)"
        meta={courses.status === "ready" ? plural(courses.data.length, "course") : undefined}
      />
      <div className="oc-panel">
        {courses.status === "loading" && <Loading label="Loading courses…" />}
        {courses.status === "error" && <LoadError error={courses.error} onRetry={courses.reload} />}
        {courses.status === "ready" &&
          (courses.data.length === 0 ? (
            <Empty title="No courses published yet" />
          ) : (
            <ul>
              {courses.data.map((c) => (
                <CourseRow
                  key={c.id}
                  course={c}
                  meta={`${DEGREE_LABEL[c.degree_level]} · ${c.duration_semesters} semesters${c.status === "archived" ? " · archived" : ""}`}
                />
              ))}
            </ul>
          ))}
      </div>
    </section>
  );
}

/** Real academic data for the signed-in member; what appears depends on their role. */
export function AcademicsPage({ institution }: { institution: ActiveInstitution }) {
  return (
    <div className="space-y-10">
      <header className="flex items-start gap-4">
        <GraduationCap className="mt-1 size-7 shrink-0 text-accent" aria-hidden="true" />
        <div>
          <p className="oc-eyebrow">{institution.name}</p>
          <h1 className="font-display text-[2.25rem] leading-none font-medium tracking-tight sm:text-[2.75rem]">Academics</h1>
        </div>
      </header>
      {institution.role === "student" && <MyCourses />}
      {institution.role === "faculty" && <Teaching />}
      {institution.role === "college_admin" && (
        <p className="rounded-xl bg-accent-soft px-4 py-3 text-sm text-ink-muted">
          Course, enrolment and timetable management is available through the API; the administration app arrives in a later release.
        </p>
      )}
      <Catalogue />
    </div>
  );
}
