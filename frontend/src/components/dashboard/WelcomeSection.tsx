import type { StudentProfile } from "../../data/types";
import { greetingFor } from "../../lib/dates";

interface WelcomeSectionProps {
  student: StudentProfile;
  today: Date;
  classesToday: number;
  dueThisWeek: number;
}

export function WelcomeSection({ student, today, classesToday, dueThisWeek }: WelcomeSectionProps) {
  const date = today.toLocaleDateString(undefined, { weekday: "long", day: "numeric", month: "long", year: "numeric" });

  return (
    <section
      aria-labelledby="welcome-title"
      className="oc-blueprint relative overflow-hidden border border-line bg-surface px-6 pt-7 pb-9 sm:px-9 sm:pt-8 sm:pb-11"
    >
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="oc-eyebrow">
          <time dateTime={today.toISOString().slice(0, 10)}>{date}</time>
        </p>
        <p className="oc-eyebrow">Demo profile</p>
      </div>

      <h1 id="welcome-title" className="mt-8 font-display text-4xl leading-[1.05] font-medium tracking-tight sm:text-[2.875rem]">
        {greetingFor(today.getHours())}, {student.firstName}.
      </h1>
      <p className="mt-3 max-w-lg text-[0.9375rem] leading-relaxed text-ink-muted">
        You have{" "}
        <strong className="font-semibold text-ink">
          {classesToday} {classesToday === 1 ? "class" : "classes"} today
        </strong>{" "}
        and{" "}
        <strong className="font-semibold text-ink">
          {dueThisWeek} {dueThisWeek === 1 ? "assignment" : "assignments"} due this week
        </strong>
        . {student.programme}, {student.year}.
      </p>

      {/* The single warm accent on the page */}
      <span className="absolute bottom-0 left-6 h-1 w-16 bg-signal sm:left-9" aria-hidden="true" />
    </section>
  );
}
