import { Check } from "lucide-react";
import type { Assignment, Subject } from "../../data/types";
import { daysBetween } from "../../lib/dates";
import { toneStyle } from "../../lib/subjects";
import { Highlight } from "../ui/Highlight";
import { NoMatches } from "../ui/NoMatches";
import { PanelHeader } from "../ui/PanelHeader";

interface AssignmentListProps {
  assignments: Assignment[];
  /** Unfiltered list, used for the completion count. */
  allAssignments: Assignment[];
  subjects: Map<string, Subject>;
  today: Date;
  query: string;
  onToggle: (id: string) => void;
}

function dueLabel(days: number): string {
  if (days < 0) return "Overdue";
  if (days === 0) return "Today";
  if (days === 1) return "Tomorrow";
  return `${days} days`;
}

export function AssignmentList({ assignments, allAssignments, subjects, today, query, onToggle }: AssignmentListProps) {
  const done = allAssignments.filter((a) => a.done).length;

  return (
    <section id="tasks" aria-labelledby="assignments-title" className="oc-panel flex h-full scroll-mt-24 flex-col">
      <PanelHeader
        id="assignments-title"
        title="Due soon"
        tone="rose"
        aside={
          <span className="font-mono" aria-live="polite">
            {done}/{allAssignments.length} done
          </span>
        }
      />

      {assignments.length === 0 ? (
        <NoMatches what="assignments" />
      ) : (
        <ul className="divide-y divide-line">
          {assignments.map((a) => {
            const subject = subjects.get(a.subjectId);
            const days = daysBetween(today, a.due);
            const urgent = !a.done && days <= 1;
            const inputId = `assignment-${a.id}`;
            return (
              <li key={a.id} style={subject ? toneStyle(subject.tone) : undefined}>
                <label
                  htmlFor={inputId}
                  className="group grid min-h-14 cursor-pointer grid-cols-[auto_1fr_auto] items-center gap-x-3 px-4 py-2.5 transition-colors hover:bg-(--tone)/[0.06] sm:px-5"
                >
                  <input id={inputId} type="checkbox" checked={a.done} onChange={() => onToggle(a.id)} className="peer sr-only" />
                  {/* 24px box inside a ≥44px row: comfortable to tap. */}
                  <span
                    className={`grid size-6 place-items-center border-2 transition-colors peer-focus-visible:outline-2 peer-focus-visible:outline-offset-2 peer-focus-visible:outline-accent ${
                      a.done ? "border-success bg-success text-white" : "border-line-strong bg-surface group-hover:border-(--tone)"
                    }`}
                    aria-hidden="true"
                  >
                    {a.done && <Check className="size-3.5" strokeWidth={3} />}
                  </span>

                  <span className="min-w-0">
                    <span className={`block truncate text-[0.9375rem] font-medium ${a.done ? "text-ink-subtle line-through" : "text-ink"}`}>
                      <Highlight text={a.title} query={query} />
                    </span>
                    <span className="mt-0.5 flex items-center gap-2 text-xs text-ink-subtle">
                      <span className="inline-flex items-center gap-1.5 font-mono">
                        <span className="size-2 rounded-full bg-(--tone)" aria-hidden="true" />
                        {subject?.code}
                      </span>
                      {a.priority === "high" && !a.done ? (
                        <span className="bg-danger-soft px-1.5 py-px font-medium text-danger">High priority</span>
                      ) : (
                        <span className="sr-only">{a.priority} priority</span>
                      )}
                    </span>
                  </span>

                  <span
                    className={`text-right text-xs font-semibold ${a.done ? "text-success" : urgent ? "text-danger" : "text-ink-muted"}`}
                  >
                    <time dateTime={a.due.toISOString().slice(0, 10)}>{a.done ? "Done" : dueLabel(days)}</time>
                  </span>
                </label>
              </li>
            );
          })}
        </ul>
      )}
    </section>
  );
}
