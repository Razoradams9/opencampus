import type { ScheduleItem, Subject } from "../../data/types";
import { formatTime, greetingFor } from "../../lib/dates";
import { SubjectMark } from "../ui/SubjectMark";
import { ArchMotif } from "./ArchMotif";
import { DayRail } from "./DayRail";

interface WelcomeSectionProps {
  firstName: string;
  institutionName: string;
  today: Date;
  now: Date;
  schedule: ScheduleItem[];
  subjects: Map<string, Subject>;
  upcoming: { item: ScheduleItem; state: "now" | "next" } | undefined;
}

/**
 * The page's dominant block: who you are, what's next, and the shape of the
 * day. Calm and focused — one message per region.
 */
export function WelcomeSection(props: WelcomeSectionProps) {
  const { firstName, institutionName, today, now, schedule, subjects, upcoming } = props;
  const date = today.toLocaleDateString(undefined, { weekday: "long", day: "numeric", month: "long" });
  const subject = upcoming ? subjects.get(upcoming.item.subjectId) : undefined;

  return (
    <section
      id="home"
      aria-labelledby="welcome-title"
      className="oc-hero relative flex h-full scroll-mt-24 flex-col overflow-hidden px-5 pt-5 pb-6 text-white sm:px-8 sm:pt-7 sm:pb-8"
    >
      <ArchMotif className="pointer-events-none absolute -right-10 -bottom-2 w-[22rem] text-white/[0.13] sm:-right-6 sm:w-[30rem]" />

      <div className="relative font-mono text-[0.6875rem] tracking-[0.1em] text-white/85 uppercase">
        <span className="truncate">{institutionName}</span>
      </div>

      <div className="relative mt-6 sm:mt-8">
        <p className="text-sm text-white/85">
          <time dateTime={today.toISOString().slice(0, 10)}>{date}</time>
        </p>
        <h1 id="welcome-title" className="mt-1 font-display text-[2.5rem] leading-[0.95] font-medium tracking-tight sm:text-[4.25rem]">
          {greetingFor(today.getHours())},
          <br />
          {firstName}.
        </h1>
      </div>

      <div className="relative mt-6 grid grid-cols-[minmax(0,1fr)] gap-4 sm:mt-auto sm:pt-8 xl:grid-cols-[minmax(0,1.25fr)_minmax(0,1fr)] xl:items-end">
        {upcoming && subject ? (
          <a
            href="#schedule"
            className="group oc-lift flex items-center gap-4 rounded-xl bg-white px-4 py-3 text-ink shadow-e2"
          >
            <span className="font-display text-[1.625rem] leading-none font-medium tabular-nums sm:text-[2rem]">{formatTime(upcoming.item.start)}</span>
            <span className="min-w-0 flex-1 pl-4">
              <span className="flex items-center gap-2 text-[0.9375rem] leading-tight font-semibold">
                <SubjectMark tone={subject.tone} className="size-3" />
                {subject.name}
              </span>
              <span className="block text-xs text-ink-muted">
                {upcoming.item.kind} · {upcoming.item.room}
              </span>
            </span>
          </a>
        ) : (
          <p className="rounded-xl bg-white/15 px-4 py-3 text-sm">No more classes today. Enjoy the evening.</p>
        )}

        <DayRail items={schedule} subjects={subjects} now={now} />
      </div>

      <span className="absolute bottom-0 left-5 h-1 w-16 rounded-t-full bg-signal sm:left-8" aria-hidden="true" />
    </section>
  );
}
