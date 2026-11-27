import { CalendarDays, ChevronLeft, ChevronRight, MapPin, UserRound } from "lucide-react";
import { useMemo, useState, type CSSProperties } from "react";
import { Empty, LoadError, Loading } from "../components/ui/DataState";
import { SubjectMark } from "../components/ui/SubjectMark";
import { toneStyle } from "../lib/subjects";
import { academicApi } from "../lib/academic/api";
import { addDaysKey, dateKey, formatClock, formatDayKey, toneFor } from "../lib/academic/format";
import type { ClassSession, TimetableWeek } from "../lib/academic/types";
import type { ActiveInstitution } from "../lib/auth/types";
import { useApi } from "../lib/useApi";

function SessionCard({ session, timeZone, showTeacher, showCourse }: {
  session: ClassSession;
  timeZone: string;
  showTeacher: boolean;
  showCourse: boolean;
}) {
  const tone = toneFor(session.subject.code);
  const cancelled = session.status === "cancelled";
  return (
    <li
      style={toneStyle(tone)}
      className={`oc-reveal rounded-lg border-l-4 px-3 py-2.5 ${
        cancelled
          ? "border-(--tone)/40 bg-sunken text-ink-subtle"
          : "oc-lift border-(--tone) bg-[color-mix(in_srgb,var(--tone)_10%,var(--oc-surface))]"
      }`}
    >
      <p className="font-mono text-[0.6875rem] text-ink-muted">
        <time dateTime={session.start_at}>{formatClock(session.start_at, timeZone)}</time>–
        <time dateTime={session.end_at}>{formatClock(session.end_at, timeZone)}</time>
        {cancelled && <span className="ml-2 font-sans font-semibold text-danger uppercase">Cancelled</span>}
      </p>
      <p className={`mt-0.5 flex items-center gap-1.5 text-sm leading-snug font-semibold ${cancelled ? "line-through" : ""}`}>
        <SubjectMark tone={tone} className="size-2.5" />
        {session.subject.name}
      </p>
      <p className="mt-0.5 font-mono text-[0.6875rem] text-ink-subtle">
        {session.subject.code}
        {showCourse && ` · ${session.course.code}`}
      </p>
      <div className="mt-1.5 flex flex-wrap gap-x-3 gap-y-0.5 text-xs text-ink-muted">
        <span className="inline-flex items-center gap-1">
          <MapPin className="size-3" aria-hidden="true" />
          {session.room ? [session.room.name, session.room.building].filter(Boolean).join(", ") : "Room to be confirmed"}
        </span>
        {showTeacher && (
          <span className="inline-flex items-center gap-1">
            <UserRound className="size-3" aria-hidden="true" />
            {session.faculty.full_name}
          </span>
        )}
      </div>
    </li>
  );
}

function WeekView({ week, role, todayKey }: { week: TimetableWeek; role: ActiveInstitution["role"]; todayKey: string }) {
  const days = useMemo(() => {
    const keys = Array.from({ length: 7 }, (_, i) => addDaysKey(week.week_start, i));
    const byDay = new Map<string, ClassSession[]>(keys.map((k) => [k, []]));
    for (const s of week.sessions) byDay.get(dateKey(s.start_at, week.timezone))?.push(s);
    return keys.map((key) => ({ key, sessions: byDay.get(key) ?? [] }));
  }, [week]);
  // Hide an empty weekend so a five-day week keeps wide columns.
  const visible = days.filter((d, i) => i < 5 || d.sessions.length > 0);

  if (week.sessions.length === 0) {
    return (
      <div className="oc-panel">
        <Empty title="No classes this week">
          {role === "college_admin" ? "No sessions are scheduled for this week." : "Nothing is scheduled for you this week."}
        </Empty>
      </div>
    );
  }

  return (
    // Phones: one column (empty days hidden). Tablets: two. Desktop: one column per day.
    <ol
      className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-(--days) lg:gap-2"
      style={{ "--days": `repeat(${visible.length}, minmax(0, 1fr))` } as CSSProperties}
    >
      {visible.map(({ key, sessions }) => {
        const isToday = key === todayKey;
        return (
          <li key={key} className={`oc-panel flex flex-col ${sessions.length === 0 ? "max-lg:hidden" : ""}`} aria-label={formatDayKey(key, { weekday: "long", day: "numeric", month: "long" })}>
            <div className={`flex items-baseline justify-between gap-2 border-b px-3 py-2.5 ${isToday ? "border-accent bg-accent-soft" : "border-line"}`}>
              <span className="font-display text-lg leading-none font-medium">{formatDayKey(key, { weekday: "short" })}</span>
              <span className={`font-mono text-xs ${isToday ? "font-semibold text-accent" : "text-ink-subtle"}`}>
                {isToday ? "Today" : formatDayKey(key, { day: "numeric", month: "short" })}
              </span>
            </div>
            {sessions.length === 0 ? (
              <p className="px-3 py-4 text-xs text-ink-subtle">No classes</p>
            ) : (
              <ul className="flex flex-col gap-2 p-2">
                {sessions.map((s) => (
                  <SessionCard
                    key={s.id}
                    session={s}
                    timeZone={week.timezone}
                    showTeacher={role !== "faculty"}
                    showCourse={role !== "student"}
                  />
                ))}
              </ul>
            )}
          </li>
        );
      })}
    </ol>
  );
}

/**
 * Weekly timetable from real scheduled sessions. Students and faculty see
 * their own week; college admins see the institution's. Times are shown in
 * the institution's timezone, which the API reports with the week.
 */
export function TimetablePage({ institution }: { institution: ActiveInstitution }) {
  const [weekOf, setWeekOf] = useState<string | null>(null);
  const scope = institution.role === "college_admin" ? "institution" : "me";
  const week = useApi((signal) => academicApi.week(scope, weekOf, signal), [scope, weekOf]);
  const timeZone = week.status === "ready" ? week.data.timezone : undefined;
  const todayKey = timeZone ? dateKey(new Date().toISOString(), timeZone) : "";
  // Keep the last known week on screen while the next one loads (no label flash).
  const [shownStart, setShownStart] = useState<string | null>(null);
  if (week.status === "ready" && week.data.week_start !== shownStart) setShownStart(week.data.week_start);
  const start = week.status === "ready" ? week.data.week_start : shownStart;

  const navButton = "grid size-9 place-items-center rounded-oc text-ink-muted transition-colors hover:bg-sunken hover:text-ink disabled:opacity-40";

  return (
    <div className="space-y-6">
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div className="flex items-start gap-4">
          <CalendarDays className="mt-1 size-7 shrink-0 text-accent" aria-hidden="true" />
          <div>
            <p className="oc-eyebrow">{scope === "institution" ? `${institution.name} · all sessions` : "Your week"}</p>
            <h1 className="font-display text-[2.25rem] leading-none font-medium tracking-tight sm:text-[2.75rem]">Timetable</h1>
          </div>
        </div>
        <nav aria-label="Week" className="flex items-center gap-1 rounded-xl bg-surface p-1 shadow-e1">
          <button type="button" className={navButton} disabled={!start} onClick={() => start && setWeekOf(addDaysKey(start, -7))} aria-label="Previous week">
            <ChevronLeft className="size-4" aria-hidden="true" />
          </button>
          <span className="min-w-[9.5rem] text-center font-mono text-xs" aria-live="polite">
            {start ? `${formatDayKey(start, { day: "numeric", month: "short" })} – ${formatDayKey(addDaysKey(start, 6), { day: "numeric", month: "short", year: "numeric" })}` : "…"}
          </span>
          <button type="button" className={navButton} disabled={!start} onClick={() => start && setWeekOf(addDaysKey(start, 7))} aria-label="Next week">
            <ChevronRight className="size-4" aria-hidden="true" />
          </button>
          <button
            type="button"
            onClick={() => setWeekOf(null)}
            disabled={weekOf === null}
            className="rounded-oc px-2.5 py-1.5 text-xs font-medium text-accent hover:bg-sunken disabled:text-ink-subtle disabled:hover:bg-transparent"
          >
            This week
          </button>
        </nav>
      </header>

      {week.status === "loading" && (
        <div className="oc-panel">
          <Loading label="Loading timetable…" />
        </div>
      )}
      {week.status === "error" && (
        <div className="oc-panel">
          <LoadError error={week.error} onRetry={week.reload} />
        </div>
      )}
      {week.status === "ready" && (
        <>
          <WeekView week={week.data} role={institution.role} todayKey={todayKey} />
          <p className="oc-eyebrow">Times shown in {week.data.timezone}</p>
        </>
      )}
    </div>
  );
}
