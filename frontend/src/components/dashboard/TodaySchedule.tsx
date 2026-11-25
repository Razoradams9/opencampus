import { MapPin } from "lucide-react";
import type { ScheduleItem, Subject } from "../../data/types";
import { formatTime } from "../../lib/dates";
import { slotStates } from "../../lib/schedule";
import { toneStyle } from "../../lib/subjects";
import { Highlight } from "../ui/Highlight";
import { NoMatches } from "../ui/NoMatches";
import { PanelHeader } from "../ui/PanelHeader";

interface TodayScheduleProps {
  items: ScheduleItem[];
  subjects: Map<string, Subject>;
  now: Date;
  totalCount: number;
  query: string;
}

export function TodaySchedule({ items, subjects, now, totalCount, query }: TodayScheduleProps) {
  const states = slotStates(items, now);

  return (
    <section id="schedule" aria-labelledby="schedule-title" className="oc-panel flex h-full scroll-mt-24 flex-col">
      <PanelHeader id="schedule-title" title="Today" tone="teal" aside={`${totalCount} classes`} />

      {items.length === 0 ? (
        <NoMatches what="classes" />
      ) : (
        <ol className="space-y-1.5 p-2 sm:p-3">
          {items.map((item) => {
            const subject = subjects.get(item.subjectId);
            const state = states.get(item.id) ?? "later";
            const featured = state === "now" || state === "next";
            return (
              <li key={item.id} style={subject ? toneStyle(subject.tone) : undefined}>
                <div
                  className={`grid grid-cols-[4.75rem_1fr] items-center gap-3 px-3 py-2.5 ${
                    featured ? "bg-(--tone) text-white" : state === "past" ? "opacity-55" : ""
                  }`}
                >
                  <div className="font-mono leading-tight whitespace-nowrap">
                    <time className="block text-sm font-medium">{formatTime(item.start)}</time>
                    <time className={`block text-[0.6875rem] ${featured ? "text-white/80" : "text-ink-subtle"}`}>
                      {formatTime(item.end)}
                    </time>
                  </div>
                  <div className={`min-w-0 border-l-[3px] pl-3 ${featured ? "border-white/60" : "border-(--tone)"}`}>
                    <p className="flex items-center gap-2 truncate text-[0.9375rem] font-semibold">
                      <Highlight text={subject?.name ?? "Class"} query={query} />
                      {featured && (
                        <span className="shrink-0 bg-white/20 px-1.5 py-px text-[0.6875rem] font-medium">
                          {state === "now" ? "Now" : "Next"}
                        </span>
                      )}
                    </p>
                    <p className={`mt-0.5 flex items-center gap-1 truncate text-xs ${featured ? "text-white/85" : "text-ink-muted"}`}>
                      <Highlight text={item.kind} query={query} />
                      <span aria-hidden="true">·</span>
                      <MapPin className="size-3 shrink-0" aria-hidden="true" />
                      <Highlight text={item.room} query={query} />
                    </p>
                  </div>
                </div>
              </li>
            );
          })}
        </ol>
      )}
    </section>
  );
}
