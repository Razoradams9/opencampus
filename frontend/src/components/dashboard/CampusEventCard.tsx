import { Clock, MapPin } from "lucide-react";
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
  const weekday = event.date.toLocaleDateString(undefined, { weekday: "long" });
  const daysAway = daysBetween(today, event.date);

  return (
    <section aria-labelledby="event-title" className="oc-panel grid overflow-hidden border-t-[3px] border-t-signal sm:grid-cols-[1fr_1.1fr]">
      <div className="flex flex-col px-5 py-5 sm:px-6 sm:py-6">
        <p className="oc-eyebrow">Upcoming event · in {daysAway} days</p>

        <div className="mt-4 flex items-start gap-4">
          <time
            dateTime={event.date.toISOString().slice(0, 10)}
            className="flex w-14 shrink-0 flex-col items-center border border-ink py-1.5"
          >
            <span className="font-mono text-[0.6875rem] tracking-widest uppercase">{month}</span>
            <span className="font-display text-3xl leading-none font-medium">{event.date.getDate()}</span>
          </time>
          <div>
            <h2 id="event-title" className="font-display text-2xl leading-tight font-medium tracking-tight">
              <Highlight text={event.title} query={query} />
            </h2>
            <p className="mt-0.5 text-xs text-ink-subtle">
              Hosted by <Highlight text={event.host} query={query} />
            </p>
          </div>
        </div>

        <p className="mt-4 text-sm leading-relaxed text-ink-muted">
          <Highlight text={event.summary} query={query} />
        </p>

        <dl className="mt-auto grid gap-1.5 pt-5 text-xs text-ink-muted">
          <div className="flex items-center gap-2">
            <dt>
              <Clock className="size-3.5" aria-label="Time" />
            </dt>
            <dd>
              {weekday}, {formatTime(event.start)} – {formatTime(event.end)}
            </dd>
          </div>
          <div className="flex items-center gap-2">
            <dt>
              <MapPin className="size-3.5" aria-label="Location" />
            </dt>
            <dd>
              <Highlight text={event.location} query={query} />
            </dd>
          </div>
        </dl>
      </div>

      <div className="oc-blueprint-wash flex items-end justify-center border-t border-line px-4 pt-6 sm:border-t-0 sm:border-l">
        <CampusIllustration className="w-full max-w-xs" />
      </div>
    </section>
  );
}
