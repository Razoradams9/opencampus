import { ArrowRight } from "lucide-react";
import type { Subject } from "../../data/types";
import { toneStyle } from "../../lib/subjects";
import { Highlight } from "../ui/Highlight";
import { NoMatches } from "../ui/NoMatches";
import { PanelHeader } from "../ui/PanelHeader";
import { SoonTag } from "../ui/SoonTag";

interface AcademicProgressProps {
  subjects: Subject[];
  /** Subject to feature as "continue learning" (first unfinished, before filtering). */
  featured: Subject | undefined;
  /** Enrolled subjects before search filtering. */
  totalCount: number;
  query: string;
}

function ProgressBar({ subject }: { subject: Subject }) {
  return (
    <div
      role="progressbar"
      aria-valuenow={subject.progress}
      aria-valuemin={0}
      aria-valuemax={100}
      aria-label={`${subject.name} progress`}
      className="h-1.5 w-full bg-sunken"
      style={toneStyle(subject.tone)}
    >
      <div className="h-full bg-(--tone)" style={{ width: `${subject.progress}%` }} />
    </div>
  );
}

export function AcademicProgress({ subjects, featured, totalCount, query }: AcademicProgressProps) {
  const showFeatured = featured && subjects.some((s) => s.id === featured.id);

  return (
    <section aria-labelledby="progress-title" className="oc-panel flex flex-col">
      <PanelHeader
        id="progress-title"
        index="Academics"
        title="Academic progress"
        aside={<span className="text-xs text-ink-subtle">{totalCount} enrolled</span>}
      />

      {showFeatured && featured && (
        <div className="border-b border-line bg-accent-soft/40 px-5 py-5 sm:px-6" style={toneStyle(featured.tone)}>
          <p className="oc-eyebrow">Next lesson</p>
          <div className="mt-2 flex flex-wrap items-end justify-between gap-4">
            <div>
              <p className="font-display text-lg font-medium">
                <Highlight text={featured.nextLesson} query={query} />
              </p>
              <p className="text-sm text-ink-muted">
                <span className="font-mono text-xs text-(--tone)">{featured.code}</span>{" "}
                <Highlight text={featured.name} query={query} />
              </p>
            </div>
            {/* Lesson content does not exist yet, so this is a disabled control. */}
            <button
              type="button"
              disabled
              className="inline-flex cursor-not-allowed items-center gap-2 border border-line-strong bg-surface px-3 py-2 text-sm font-medium text-ink-subtle"
            >
              Continue learning <ArrowRight className="size-4" aria-hidden="true" />
              <SoonTag />
            </button>
          </div>
        </div>
      )}

      {subjects.length === 0 ? (
        <NoMatches what="subjects" />
      ) : (
        <ul className="divide-y divide-line">
          {subjects.map((subject) => (
            <li key={subject.id} className="grid grid-cols-[1fr_auto] gap-x-4 gap-y-2 px-5 py-3.5 sm:px-6" style={toneStyle(subject.tone)}>
              <div className="min-w-0">
                <p className="truncate text-sm font-medium">
                  <span className="mr-2 font-mono text-xs text-(--tone)">{subject.code}</span>
                  <Highlight text={subject.name} query={query} />
                </p>
                <p className="mt-0.5 truncate text-xs text-ink-subtle">
                  Next: <Highlight text={subject.nextLesson} query={query} />
                </p>
              </div>
              <p className="self-center text-right font-mono text-sm">
                {subject.progress}%
                <span className="block text-[0.6875rem] text-ink-subtle">
                  {subject.lessonsCompleted}/{subject.lessonsTotal} lessons
                </span>
              </p>
              <div className="col-span-2">
                <ProgressBar subject={subject} />
              </div>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
