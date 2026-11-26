import { Check, ChevronDown } from "lucide-react";
import { useState } from "react";
import type { Assignment, Subject } from "../../data/types";
import { daysBetween } from "../../lib/dates";
import { toneStyle } from "../../lib/subjects";
import { Highlight } from "../ui/Highlight";
import { NoMatches } from "../ui/NoMatches";
import { SectionHeading } from "../ui/SectionHeading";
import { SubjectMark } from "../ui/SubjectMark";
import { WeekLoad } from "./WeekLoad";

interface AssignmentListProps {
  assignments: Assignment[];
  /** Unfiltered list, used for the completion count. */
  allAssignments: Assignment[];
  subjects: Map<string, Subject>;
  today: Date;
  query: string;
  searching: boolean;
  onToggle: (id: string) => void;
}

/** Shown before "Show all": enough to act on, few enough to not overwhelm. */
const COLLAPSED_COUNT = 3;

function dueLabel(days: number): string {
  if (days < 0) return "Overdue";
  if (days === 0) return "Today";
  if (days === 1) return "Tomorrow";
  return `${days} days`;
}

/**
 * Calm by default: red is reserved for overdue work; "today/tomorrow" use the
 * interface accent. Priority gets a soft marker, not an alarm.
 */
function dueTone(days: number, done: boolean): string {
  if (done) return "text-success";
  if (days < 0) return "text-danger";
  if (days <= 1) return "text-accent";
  return "text-ink-muted";
}

export function AssignmentList({ assignments, allAssignments, subjects, today, query, searching, onToggle }: AssignmentListProps) {
  const [expanded, setExpanded] = useState(false);
  const [justChecked, setJustChecked] = useState<string | null>(null);
  const done = allAssignments.filter((a) => a.done).length;
  const allDone = done === allAssignments.length && allAssignments.length > 0;

  // Stable order (by due date) so rows never jump when ticked.
  const sorted = [...assignments].sort((a, b) => a.due.getTime() - b.due.getTime());
  const visible = searching || expanded ? sorted : sorted.slice(0, COLLAPSED_COUNT);
  const hidden = sorted.length - visible.length;

  return (
    <section id="tasks" aria-labelledby="assignments-title" className="flex h-full scroll-mt-24 flex-col">
      <SectionHeading
        id="assignments-title"
        title="Due soon"
        accent="var(--oc-subject-rose)"
        meta={
          <span aria-live="polite">
            {allDone ? <span className="font-semibold text-success">All caught up</span> : `${done} of ${allAssignments.length} done`}
          </span>
        }
      />
      <div className="oc-panel flex flex-1 flex-col">
      {!searching && (
        <div className="border-b border-line/70 p-2 sm:p-3">
          <WeekLoad assignments={allAssignments} subjects={subjects} today={today} />
        </div>
      )}

      {assignments.length === 0 ? (
        <NoMatches what="assignments" />
      ) : (
        <ul className="space-y-1 p-2">
          {visible.map((a) => {
            const subject = subjects.get(a.subjectId);
            const days = daysBetween(today, a.due);
            const inputId = `assignment-${a.id}`;
            return (
              <li key={a.id} style={subject ? toneStyle(subject.tone) : undefined}>
                <label
                  htmlFor={inputId}
                  className="group grid min-h-14 cursor-pointer grid-cols-[auto_1fr_auto] items-center gap-x-3 rounded-xl px-3 py-2.5 transition-colors hover:bg-(--tone)/[0.07]"
                >
                  <input
                    id={inputId}
                    type="checkbox"
                    checked={a.done}
                    onChange={() => {
                      if (!a.done) setJustChecked(a.id);
                      onToggle(a.id);
                    }}
                    className="peer sr-only"
                  />
                  <span
                    className={`grid size-6 place-items-center rounded-md border-2 transition-colors peer-focus-visible:outline-2 peer-focus-visible:outline-offset-2 peer-focus-visible:outline-accent ${
                      a.done ? "border-success bg-success text-white" : "border-line-strong bg-surface group-hover:border-(--tone)"
                    } ${a.done && justChecked === a.id ? "oc-pop" : ""}`}
                    aria-hidden="true"
                  >
                    {a.done && <Check className="size-3.5" strokeWidth={3} />}
                  </span>

                  <span className="min-w-0">
                    <span className={`block truncate text-[0.9375rem] font-medium transition-colors ${a.done ? "text-ink-subtle line-through" : "text-ink"}`}>
                      <Highlight text={a.title} query={query} />
                    </span>
                    <span className="mt-0.5 flex items-center gap-2 text-xs text-ink-subtle">
                      <span className="inline-flex items-center gap-1.5 font-mono">
                        {subject && <SubjectMark tone={subject.tone} className="size-2.5" />}
                        {subject?.code}
                      </span>
                      {a.priority === "high" && !a.done ? (
                        <span className="rounded-full bg-pending-soft px-2 py-px font-medium text-pending">Priority</span>
                      ) : (
                        <span className="sr-only">{a.priority} priority</span>
                      )}
                    </span>
                  </span>

                  <span className={`text-right text-xs font-semibold ${dueTone(days, a.done)}`}>
                    <time dateTime={a.due.toISOString().slice(0, 10)}>{a.done ? "Done" : dueLabel(days)}</time>
                  </span>
                </label>
              </li>
            );
          })}
        </ul>
      )}

      {!searching && sorted.length > COLLAPSED_COUNT && (
        <button
          type="button"
          onClick={() => setExpanded((v) => !v)}
          aria-expanded={expanded}
          className="mt-auto flex min-h-11 items-center justify-center gap-1.5 border-t border-line/70 text-sm font-medium text-accent transition-colors hover:bg-accent-soft/50"
        >
          {expanded ? "Show less" : `Show all ${sorted.length}`}
          <ChevronDown className={`size-4 transition-transform ${expanded ? "rotate-180" : ""}`} aria-hidden="true" />
          {!expanded && <span className="sr-only">({hidden} more)</span>}
        </button>
      )}
      </div>
    </section>
  );
}
