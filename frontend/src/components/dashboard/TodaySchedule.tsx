import { MapPin } from "lucide-react";
import type { ScheduleItem, Subject } from "../../data/types";
import { formatTime, toMinutes } from "../../lib/dates";
import { toneStyle } from "../../lib/subjects";
import { Highlight } from "../ui/Highlight";
import { NoMatches } from "../ui/NoMatches";
import { PanelHeader } from "../ui/PanelHeader";

interface TodayScheduleProps {
  items: ScheduleItem[];
  subjects: Map<string, Subject>;
  now: Date;
  /** Classes today before search filtering. */
  totalCount: number;
  query: string;
}

type SlotState = "past" | "now" | "next" | "later";

function slotStates(items: ScheduleItem[], now: Date): Map<string, SlotState> {
  const minutes = now.getHours() * 60 + now.getMinutes();
  const states = new Map<string, SlotState>();
  let nextAssigned = false;
  for (const item of [...items].sort((a, b) => toMinutes(a.start) - toMinutes(b.start))) {
    if (toMinutes(item.end) <= minutes) states.set(item.id, "past");
    else if (toMinutes(item.start) <= minutes) states.set(item.id, "now");
    else if (!nextAssigned) {
      states.set(item.id, "next");
      nextAssigned = true;
    } else states.set(item.id, "later");
  }
  return states;
}

const STATE_LABEL: Partial<Record<SlotState, string>> = { now: "In progress", next: "Up next" };

export function TodaySchedule({ items, subjects, now, totalCount, query }: TodayScheduleProps) {
  const states = slotStates(items, now);

  return (
    <section aria-labelledby="schedule-title" className="oc-panel flex flex-col">
      <PanelHeader
        id="schedule-title"
        index="Timetable"
        title="Today's schedule"
        aside={<span className="text-xs text-ink-subtle">{totalCount} {totalCount === 1 ? "class" : "classes"}</span>}
      />

      {items.length === 0 ? (
        <NoMatches what="classes" />
      ) : (
        <ol className="px-5 py-4 sm:px-6">
          {items.map((item, i) => {
            const subject = subjects.get(item.subjectId);
            const state = states.get(item.id) ?? "later";
            const label = STATE_LABEL[state];
            const isLast = i === items.length - 1;
            return (
              <li
                key={item.id}
                className={`grid grid-cols-[4.25rem_1rem_1fr] gap-x-3 ${state === "past" ? "opacity-60" : ""}`}
                style={subject ? toneStyle(subject.tone) : undefined}
              >
                <div className="pt-0.5 text-right font-mono text-xs leading-5">
                  <time className="block text-ink">{formatTime(item.start)}</time>
                  <time className="block text-ink-subtle">{formatTime(item.end)}</time>
                </div>

                {/* Timeline rail */}
                <div className="relative flex justify-center" aria-hidden="true">
                  <span
                    className={`relative z-10 mt-1.5 size-2.5 border-2 border-(--tone) ${
                      state === "now" || state === "next" ? "bg-(--tone)" : "bg-surface"
                    }`}
                  />
                  {!isLast && <span className="absolute top-4 bottom-0 w-px bg-line-strong" />}
                </div>

                <div className={isLast ? "pb-1" : "pb-5"}>
                  <div className="flex flex-wrap items-center gap-2">
                    <p className="text-sm font-semibold">
                      <Highlight text={subject?.name ?? "Class"} query={query} />
                    </p>
                    {label && (
                      <span
                        className={`px-1.5 py-px text-[0.6875rem] font-medium ${
                          state === "now" ? "bg-success-soft text-success" : "bg-accent-soft text-accent"
                        }`}
                      >
                        {label}
                      </span>
                    )}
                  </div>
                  <p className="text-xs text-ink-muted">
                    <Highlight text={item.kind} query={query} /> · <Highlight text={item.instructor} query={query} />
                  </p>
                  <p className="mt-1 flex items-center gap-1 text-xs text-ink-subtle">
                    <MapPin className="size-3.5 shrink-0" aria-hidden="true" />
                    <span>
                      <Highlight text={item.room} query={query} />, <Highlight text={item.building} query={query} />
                    </span>
                  </p>
                </div>
              </li>
            );
          })}
        </ol>
      )}
    </section>
  );
}
