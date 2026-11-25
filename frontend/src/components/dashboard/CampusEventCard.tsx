import { MapPin } from "lucide-react";
import type { CampusEvent } from "../../data/types";
import { daysBetween, formatTime } from "../../lib/dates";
import { Highlight } from "../ui/Highlight";
import { CampusIllustration } from "./CampusIllustration";

interface CampusEventCardProps {
  event: CampusEvent;
  today: Date;
  query: string;
}

export function CampusEventCard({ event, today, query }: CampusEventCardProps) {
  const month = event.date.toLocaleDateString(undefined, { month: "short" });
  const weekday = event.date.toLocaleDateString(undefined, { weekday: "short" });
  const daysAway = daysBetween(today, event.date);

  return (
    <section aria-labelledby="event-title" className="oc-panel grid h-full overflow-hidden sm:grid-cols-[1fr_1fr]">
      <div className="flex flex-col gap-4 p-4 sm:p-5">
        <div className="flex items-start gap-3">
          <time
            dateTime={event.date.toISOString().slice(0, 10)}
            className="flex w-14 shrink-0 flex-col items-center rounded-xl bg-signal-strong py-1.5 text-white shadow-e2"
          >
            <span className="font-mono text-[0.6875rem] tracking-widest uppercase">{month}</span>
            <span className="font-display text-3xl leading-none font-medium">{event.date.getDate()}</span>
          </time>
          <div className="min-w-0">
            <p className="text-[0.6875rem] font-semibold tracking-wide text-signal-strong uppercase">In {daysAway} days</p>
            <h2 id="event-title" className="font-display text-xl leading-tight font-medium tracking-tight sm:text-2xl">
              <Highlight text={event.title} query={query} />
            </h2>
          </div>
        </div>
        <p className="text-sm text-ink-muted">
          <Highlight text={event.summary} query={query} />
        </p>
        <p className="mt-auto flex items-center gap-1.5 text-xs font-medium text-ink-muted">
          <MapPin className="size-3.5 shrink-0" aria-hidden="true" />
          {weekday} {formatTime(event.start)} · <Highlight text={event.location} query={query} />
        </p>
      </div>
      <div className="oc-blueprint-wash hidden items-end justify-center border-l border-line px-4 pt-6 sm:flex">
        <CampusIllustration className="w-full max-w-xs" />
      </div>
    </section>
  );
}
