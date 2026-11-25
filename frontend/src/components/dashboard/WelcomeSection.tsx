import { ArrowRight, Moon, Sun, Sunrise } from "lucide-react";
import type { ScheduleItem, Subject } from "../../data/types";
import { formatTime, greetingFor } from "../../lib/dates";

interface WelcomeSectionProps {
  firstName: string;
  institutionName: string;
  today: Date;
  upcoming: { item: ScheduleItem; state: "now" | "next" } | undefined;
  subject: Subject | undefined;
  dueThisWeek: number;
}

function TimeIcon({ hour }: { hour: number }) {
  const Icon = hour < 12 ? Sunrise : hour < 18 ? Sun : Moon;
  return <Icon className="size-5 text-signal" aria-hidden="true" />;
}

/** Greeting plus the two things a student checks first: next class, what's due. */
export function WelcomeSection({ firstName, institutionName, today, upcoming, subject, dueThisWeek }: WelcomeSectionProps) {
  const date = today.toLocaleDateString(undefined, { weekday: "short", day: "numeric", month: "short" });

  return (
    <section
      id="home"
      aria-labelledby="welcome-title"
      className="oc-hero relative flex h-full scroll-mt-24 flex-col overflow-hidden px-5 pt-5 pb-6 text-white sm:px-8 sm:pt-7 sm:pb-8"
    >
      <div className="flex items-center justify-between gap-3 font-mono text-[0.6875rem] tracking-[0.1em] text-white/85 uppercase">
        <span className="truncate">
          <time dateTime={today.toISOString().slice(0, 10)}>{date}</time> · {institutionName}
        </span>
        <span className="shrink-0 border border-white/40 px-1.5 py-px">Sample data</span>
      </div>

      <h1
        id="welcome-title"
        className="mt-6 flex items-center gap-3 font-display text-[2rem] leading-tight font-medium tracking-tight sm:mt-10 sm:text-5xl"
      >
        <span>
          {greetingFor(today.getHours())}, {firstName}.
        </span>
        <TimeIcon hour={today.getHours()} />
      </h1>

      <div className="mt-5 flex flex-wrap gap-2 sm:mt-auto sm:pt-8">
        {upcoming && subject ? (
          <a
            href="#schedule"
            className="group flex w-full items-center gap-3 bg-white px-3 py-2 text-ink transition-colors hover:bg-canvas sm:w-auto sm:min-w-72"
          >
            <span className="min-w-0 flex-1">
              <span className="block text-xs text-ink-muted">
                <span className="font-semibold text-hero">{upcoming.state === "now" ? "Now" : "Next"}</span> ·{" "}
                <span className="font-mono">{formatTime(upcoming.item.start)}</span> · {upcoming.item.room}
              </span>
              <span className="block truncate text-[0.9375rem] font-semibold">{subject.name}</span>
            </span>
            <ArrowRight className="size-4 shrink-0 text-ink-muted transition-transform group-hover:translate-x-0.5" aria-hidden="true" />
          </a>
        ) : (
          <span className="bg-white/15 px-3 py-2 text-sm">No more classes today</span>
        )}
        <a href="#tasks" className="inline-flex min-h-11 items-center gap-2 bg-white/15 px-3 py-2 text-sm transition-colors hover:bg-white/25">
          <span className="font-semibold">{dueThisWeek}</span> due this week
        </a>
      </div>

      <span className="absolute bottom-0 left-5 h-1 w-16 bg-signal sm:left-8" aria-hidden="true" />
    </section>
  );
}
