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

/** Poster treatment on the warm apricot block: the page's warm counterweight. */
export function CampusEventCard({ event, today, query }: CampusEventCardProps) {
  const month = event.date.toLocaleDateString(undefined, { month: "long" });
  const weekday = event.date.toLocaleDateString(undefined, { weekday: "long" });
  const daysAway = daysBetween(today, event.date);

  return (
    <section
      aria-labelledby="event-title"
      className="relative grid h-full overflow-hidden rounded-card bg-apricot shadow-e1 sm:grid-cols-[minmax(0,1fr)_minmax(0,0.9fr)]"
    >
      <div className="relative z-[1] flex flex-col p-5 sm:p-7">
        <p className="font-mono text-[0.6875rem] font-medium tracking-[0.12em] text-apricot-ink uppercase">
          Upcoming event · in {daysAway} days
        </p>
        <div className="mt-3 flex items-end gap-3">
          <time dateTime={event.date.toISOString().slice(0, 10)} className="font-display text-[5rem] leading-[0.8] font-medium text-signal-strong tabular-nums">
            {event.date.getDate()}
          </time>
          <span className="pb-1 text-sm leading-tight font-semibold text-apricot-ink">
            {month}
            <br />
            {weekday}
          </span>
        </div>
        <h2 id="event-title" className="mt-4 font-display text-[1.875rem] leading-tight font-medium tracking-tight">
          <Highlight text={event.title} query={query} />
        </h2>
        <p className="mt-1.5 max-w-sm text-sm text-ink-muted">
          <Highlight text={event.summary} query={query} />
        </p>
        <p className="mt-5 flex items-center gap-1.5 text-sm font-medium">
          <MapPin className="size-4 shrink-0 text-apricot-ink" aria-hidden="true" />
          {formatTime(event.start)} · <Highlight text={event.location} query={query} />
        </p>
      </div>
      <div className="hidden items-end justify-center px-4 pt-6 sm:flex">
        <CampusIllustration className="w-full max-w-xs" />
      </div>
    </section>
  );
}
