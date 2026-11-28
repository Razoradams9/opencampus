import { SubjectMark } from "../ui/SubjectMark";
import { toneFor } from "../../lib/academic/format";
import type { MySubject } from "../../lib/academic/types";

/**
 * Subject index: an editorial numbered list on desktop, a horizontal chip
 * scroller on phones. `counts` adds a small figure per subject.
 */
export function SubjectRail({
  subjects,
  selected,
  onSelect,
  counts,
  label,
}: {
  subjects: MySubject[];
  selected: string | null;
  onSelect: (subjectId: string) => void;
  counts?: Map<string, number>;
  label: string;
}) {
  return (
    <nav aria-label={label} className="min-w-0">
      <ul className="oc-scroll-x -mx-4 flex gap-2 px-4 pb-1 lg:mx-0 lg:block lg:space-y-1 lg:px-0">
        {subjects.map(({ subject, course }, index) => {
          const current = subject.id === selected;
          return (
            <li key={subject.id} className="shrink-0">
              <button
                type="button"
                onClick={() => onSelect(subject.id)}
                aria-current={current ? "true" : undefined}
                className={`flex w-full items-center gap-3 rounded-xl px-3 py-2.5 text-left transition-colors duration-150 ${
                  current ? "bg-surface shadow-e1 ring-1 ring-accent/20" : "hover:bg-surface/70"
                }`}
              >
                <span className="hidden w-6 font-mono text-xs text-ink-subtle lg:inline">{String(index + 1).padStart(2, "0")}</span>
                <SubjectMark tone={toneFor(subject.code)} className="size-3" />
                <span className="min-w-0 flex-1">
                  <span className={`block text-sm whitespace-nowrap lg:truncate lg:whitespace-normal ${current ? "font-semibold text-ink" : "font-medium text-ink-muted"}`}>
                    {subject.name}
                  </span>
                  <span className="block font-mono text-[0.6875rem] text-ink-subtle">
                    {subject.code} · {course.code}
                  </span>
                </span>
                {counts && <span className="font-mono text-xs text-ink-subtle">{counts.get(subject.id) ?? 0}</span>}
              </button>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}
