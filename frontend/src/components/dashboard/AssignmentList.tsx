import { Check } from "lucide-react";
import type { Assignment, Priority, Subject } from "../../data/types";
import { formatDueLabel, formatShortDate, daysBetween } from "../../lib/dates";
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

// Priority is shown as text and a bar pattern, never colour alone.
const PRIORITY: Record<Priority, { label: string; bars: number; tone: string }> = {
  high: { label: "High", bars: 3, tone: "bg-danger" },
  medium: { label: "Medium", bars: 2, tone: "bg-pending" },
  low: { label: "Low", bars: 1, tone: "bg-ink-subtle" },
};

function PriorityIndicator({ priority }: { priority: Priority }) {
  const p = PRIORITY[priority];
  return (
    <span className="inline-flex items-center gap-1.5 text-[0.6875rem] text-ink-muted">
      <span className="flex items-end gap-px" aria-hidden="true">
        {[1, 2, 3].map((n) => (
          <span key={n} className={`w-[3px] ${n <= p.bars ? p.tone : "bg-line-strong"}`} style={{ height: `${4 + n * 3}px` }} />
        ))}
      </span>
      {p.label}
    </span>
  );
}

export function AssignmentList({ assignments, allAssignments, subjects, today, query, onToggle }: AssignmentListProps) {
  const done = allAssignments.filter((a) => a.done).length;

  return (
    <section aria-labelledby="assignments-title" className="oc-panel flex flex-col">
      <PanelHeader
        id="assignments-title"
        index="Assignments"
        title="Due soon"
        aside={
          <span className="font-mono text-xs text-ink-subtle" aria-live="polite">
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
                  className="group grid cursor-pointer grid-cols-[auto_1fr_auto] items-start gap-x-3 px-5 py-3.5 transition-colors hover:bg-sunken/50 sm:px-6"
                >
                  <input
                    id={inputId}
                    type="checkbox"
                    checked={a.done}
                    onChange={() => onToggle(a.id)}
                    className="peer sr-only"
                  />
                  {/* Custom checkbox; focus ring follows the real (visually hidden) input */}
                  <span
                    className={`mt-0.5 grid size-[1.125rem] place-items-center border-[1.5px] transition-colors peer-focus-visible:outline-2 peer-focus-visible:outline-offset-2 peer-focus-visible:outline-accent ${
                      a.done ? "border-success bg-success text-surface" : "border-line-strong bg-surface group-hover:border-ink-subtle"
                    }`}
                    aria-hidden="true"
                  >
                    {a.done && <Check className="size-3" strokeWidth={3} />}
                  </span>

                  <span className="min-w-0">
                    <span className={`block text-sm font-medium ${a.done ? "text-ink-subtle line-through" : "text-ink"}`}>
                      <Highlight text={a.title} query={query} />
                    </span>
                    <span className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-ink-subtle">
                      <span className="inline-flex items-center gap-1.5">
                        <span className="size-1.5 bg-(--tone)" aria-hidden="true" />
                        <span className="font-mono">{subject?.code}</span>
                      </span>
                      <PriorityIndicator priority={a.priority} />
                    </span>
                  </span>

                  <span className="text-right text-xs">
                    <span className={`block font-medium ${a.done ? "text-success" : urgent ? "text-danger" : "text-ink-muted"}`}>
                      {a.done ? "Completed" : formatDueLabel(a.due, today)}
                    </span>
                    <time dateTime={a.due.toISOString().slice(0, 10)} className="font-mono text-ink-subtle">
                      {formatShortDate(a.due)}
                    </time>
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
