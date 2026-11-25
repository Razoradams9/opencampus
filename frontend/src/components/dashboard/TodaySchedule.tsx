import type { ScheduleItem, Subject } from "../../data/types";
import { formatTime, toMinutes } from "../../lib/dates";
import { slotStates } from "../../lib/schedule";
import { toneStyle } from "../../lib/subjects";
import { Highlight } from "../ui/Highlight";
import { NoMatches } from "../ui/NoMatches";
import { SectionHeading } from "../ui/SectionHeading";
import { SubjectMark } from "../ui/SubjectMark";

interface TodayScheduleProps {
  items: ScheduleItem[];
  subjects: Map<string, Subject>;
  now: Date;
  totalCount: number;
  query: string;
}

/** Vertical pixels per minute: a one-hour class is 68px tall. */
const PX_PER_MIN = 68 / 60;

/**
 * A proportional day view: block height is class length, so the shape of
 * the day (long labs, free gaps) is visible at a glance.
 */
export function TodaySchedule({ items, subjects, now, totalCount, query }: TodayScheduleProps) {
  const states = slotStates(items, now);
  const hasCurrent = [...states.values()].includes("now");

  const start = items.length ? Math.floor(Math.min(...items.map((i) => toMinutes(i.start))) / 60) * 60 : 0;
  const end = items.length ? Math.ceil(Math.max(...items.map((i) => toMinutes(i.end))) / 60) * 60 : 0;
  const hours = Array.from({ length: (end - start) / 60 + 1 }, (_, i) => start + i * 60);
  const nowMinutes = now.getHours() * 60 + now.getMinutes();

  return (
    <section id="schedule" aria-labelledby="schedule-title" className="flex h-full scroll-mt-24 flex-col">
      <SectionHeading id="schedule-title" title="Today" accent="var(--oc-subject-teal)" meta={`${totalCount} classes`} />

      <div className="oc-panel flex-1 p-3 sm:p-4">
        {items.length === 0 ? (
          <NoMatches what="classes" />
        ) : (
          <ol className="relative ml-[4.25rem]" style={{ height: (end - start) * PX_PER_MIN }}>
            {hours.map((h) => (
              <li key={`h${h}`} aria-hidden="true" className="absolute inset-x-0" style={{ top: (h - start) * PX_PER_MIN }}>
                <span className="absolute -left-[4.25rem] w-[3.75rem] -translate-y-1/2 text-right font-mono text-[0.6875rem] whitespace-nowrap text-ink-subtle">
                  {formatTime(`${String(h / 60).padStart(2, "0")}:00`)}
                </span>
                <span className="block border-t border-dashed border-line" />
              </li>
            ))}

            {items.map((item) => {
              const subject = subjects.get(item.subjectId);
              const state = states.get(item.id) ?? "later";
              const featured = state === "now" || (state === "next" && !hasCurrent);
              const top = (toMinutes(item.start) - start) * PX_PER_MIN;
              const height = (toMinutes(item.end) - toMinutes(item.start)) * PX_PER_MIN;
              return (
                <li
                  key={item.id}
                  style={{ ...(subject ? toneStyle(subject.tone) : {}), top: top + 2, height: height - 4 }}
                  className={`absolute right-0 left-1 flex flex-col justify-center overflow-hidden rounded-lg border-l-4 px-3 ${
                    featured
                      ? "oc-raised z-[1] border-white/50 bg-(--tone) text-white"
                      : state === "past"
                        ? "border-(--tone)/40 bg-[color-mix(in_srgb,var(--oc-surface-sunken)_55%,var(--oc-surface))] text-ink-subtle"
                        : "border-(--tone) bg-[color-mix(in_srgb,var(--tone)_10%,var(--oc-surface))]"
                  }`}
                >
                  <p className="flex items-center gap-2 truncate text-[0.9375rem] font-semibold">
                    {subject && !featured && <SubjectMark tone={subject.tone} className="size-2.5" />}
                    <Highlight text={subject?.name ?? "Class"} query={query} />
                    {featured && (
                      <span className="shrink-0 rounded-full bg-white/20 px-2 py-px text-[0.6875rem] font-medium">
                        {state === "now" ? "Now" : "Next"}
                      </span>
                    )}
                  </p>
                  <p className={`truncate text-xs ${featured ? "text-white/85" : "text-ink-muted"}`}>
                    <span className="font-mono">
                      {formatTime(item.start)}–{formatTime(item.end)}
                    </span>{" "}
                    · <Highlight text={item.kind} query={query} /> · <Highlight text={item.room} query={query} />
                  </p>
                </li>
              );
            })}

            {nowMinutes > start && nowMinutes < end && (
              <li aria-hidden="true" className="absolute inset-x-0 z-[2]" style={{ top: (nowMinutes - start) * PX_PER_MIN }}>
                <span className="absolute -left-1.5 -top-1 size-2 rounded-full bg-signal" />
                <span className="block h-0.5 bg-signal" />
              </li>
            )}
          </ol>
        )}
      </div>
    </section>
  );
}
