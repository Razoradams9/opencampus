import type { Assignment, Subject } from "../../data/types";
import { addDays, daysBetween } from "../../lib/dates";
import { SubjectMark } from "../ui/SubjectMark";

interface WeekLoadProps {
  assignments: Assignment[];
  subjects: Map<string, Subject>;
  today: Date;
}

/**
 * The next seven days, with each task as its subject's shape on the day it
 * is due (hollow once done). Shows where the week is heavy at a glance.
 */
export function WeekLoad({ assignments, subjects, today }: WeekLoadProps) {
  const days = Array.from({ length: 7 }, (_, i) => addDays(today, i));

  return (
    <ol className="grid grid-cols-7 gap-1" aria-label="Tasks due over the next seven days">
      {days.map((day, i) => {
        const due = assignments.filter((a) => daysBetween(today, a.due) === i);
        const open = due.filter((a) => !a.done).length;
        const label = day.toLocaleDateString(undefined, { weekday: "short" });
        return (
          <li
            key={i}
            className={`flex min-h-[5.25rem] flex-col items-center rounded-lg px-0.5 pt-1.5 pb-2 ${i === 0 ? "bg-subject-rose/12" : "bg-canvas/60"}`}
          >
            <span className={`text-[0.6875rem] font-medium ${i === 0 ? "text-subject-rose" : "text-ink-subtle"}`}>{i === 0 ? "Today" : label}</span>
            <span className="font-display text-lg leading-tight font-medium tabular-nums">{day.getDate()}</span>
            <span className="mt-auto flex flex-wrap justify-center gap-0.5" aria-hidden="true">
              {due.map((a) => {
                const tone = subjects.get(a.subjectId)?.tone;
                return tone ? <SubjectMark key={a.id} tone={tone} hollow={a.done} className="size-3" /> : null;
              })}
            </span>
            <span className="sr-only">
              {label} {day.getDate()}: {due.length === 0 ? "nothing due" : `${due.length} due, ${open} open`}
            </span>
          </li>
        );
      })}
    </ol>
  );
}
