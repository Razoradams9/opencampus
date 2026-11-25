import type { ScheduleItem, Subject } from "../../data/types";
import { formatTime, toMinutes } from "../../lib/dates";
import { slotStates } from "../../lib/schedule";

interface DayRailProps {
  items: ScheduleItem[];
  subjects: Map<string, Subject>;
  now: Date;
}

/**
 * Today at a glance: classes as segments between the first and last hour,
 * with the current time marked. Shows load and gaps, not decoration.
 */
export function DayRail({ items, subjects, now }: DayRailProps) {
  if (items.length === 0) return null;
  const start = Math.floor(Math.min(...items.map((i) => toMinutes(i.start))) / 60) * 60;
  const end = Math.ceil(Math.max(...items.map((i) => toMinutes(i.end))) / 60) * 60;
  const span = end - start;
  const nowMinutes = now.getHours() * 60 + now.getMinutes();
  const states = slotStates(items, now);
  const pct = (minutes: number) => `${((minutes - start) / span) * 100}%`;
  const label = (minutes: number) => formatTime(`${String(Math.floor(minutes / 60)).padStart(2, "0")}:00`);

  return (
    <figure className="w-full">
      <figcaption className="sr-only">
        Today: {items.map((i) => `${subjects.get(i.subjectId)?.name} ${formatTime(i.start)} to ${formatTime(i.end)}`).join("; ")}
      </figcaption>
      <div className="relative h-7" aria-hidden="true">
        <div className="absolute inset-x-0 top-1/2 h-px -translate-y-1/2 bg-white/30" />
        {items.map((item) => {
          const state = states.get(item.id);
          const left = toMinutes(item.start);
          const width = toMinutes(item.end) - left;
          return (
            <div
              key={item.id}
              className={`absolute top-1 bottom-1 rounded-[3px] ${
                state === "past" ? "bg-white/25" : state === "now" ? "bg-white" : "bg-white/60"
              }`}
              style={{ left: pct(left), width: `calc(${(width / span) * 100}% - 3px)` }}
            />
          );
        })}
        {nowMinutes > start && nowMinutes < end && (
          <div className="absolute -top-1 -bottom-1 w-0.5 rounded-full bg-signal" style={{ left: pct(nowMinutes) }}>
            <span className="absolute -top-1 -left-[3px] size-2 rounded-full bg-signal" />
          </div>
        )}
      </div>
      <div className="mt-1.5 flex justify-between font-mono text-[0.6875rem] text-white/80" aria-hidden="true">
        <span>{label(start)}</span>
        <span>{label(end)}</span>
      </div>
    </figure>
  );
}
