import { relativeDeadline, elapsed, formatDateTime } from "../../lib/academic/deadlines";
import type { Coursework } from "../../lib/academic/types";

const WINDOW_TEXT = { not_open: "Not open yet", open: "Open", late: "Late window", closed: "Closed" } as const;

/** Deadline as words plus a bar of the working window already used. */
export function DeadlineBar({ a, compact = false }: { a: Coursework; compact?: boolean }) {
  const used = elapsed(a);
  const overdue = new Date(a.due_at).getTime() < Date.now();
  const tone = overdue ? "var(--oc-danger)" : used > 0.8 ? "var(--oc-subject-amber)" : "var(--oc-subject-teal)";
  return (
    <div className={compact ? "w-full sm:w-44" : ""}>
      <div className="flex items-baseline justify-between gap-2">
        <span className="text-xs font-semibold" style={{ color: tone }}>{relativeDeadline(a.due_at)}</span>
        {!compact && <span className="font-mono text-[0.6875rem] text-ink-subtle">{WINDOW_TEXT[a.window]}</span>}
      </div>
      <div className="mt-1 h-1.5 overflow-hidden rounded-full bg-sunken" role="img" aria-label={`${Math.round(used * 100)}% of the working time used`}>
        <div className="h-full rounded-full transition-[width] duration-500" style={{ width: `${Math.max(4, used * 100)}%`, background: tone }} />
      </div>
      <p className="mt-1 font-mono text-[0.6875rem] text-ink-subtle">{formatDateTime(a.due_at)}</p>
    </div>
  );
}

export function GradeBadge({ marks, max }: { marks: number; max: number }) {
  const pct = max > 0 ? marks / max : 0;
  return (
    <span className="inline-flex items-baseline gap-0.5 font-display text-2xl leading-none font-medium text-ink">
      {marks}
      <span className="font-sans text-xs text-ink-subtle">/{max}</span>
      <span className="sr-only">({Math.round(pct * 100)}%)</span>
    </span>
  );
}
