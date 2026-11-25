import { ArrowRight } from "lucide-react";
import type { Subject } from "../../data/types";
import { toneStyle } from "../../lib/subjects";
import { Highlight } from "../ui/Highlight";
import { NoMatches } from "../ui/NoMatches";
import { PanelHeader } from "../ui/PanelHeader";

interface AcademicProgressProps {
  subjects: Subject[];
  /** Subject featured as "next lesson" (first unfinished, before filtering). */
  featured: Subject | undefined;
  totalCount: number;
  query: string;
}

function ProgressRing({ subject }: { subject: Subject }) {
  const radius = 22;
  const circumference = 2 * Math.PI * radius;
  return (
    <div
      role="progressbar"
      aria-valuenow={subject.progress}
      aria-valuemin={0}
      aria-valuemax={100}
      aria-label={`${subject.name} progress`}
      className="relative size-14 shrink-0"
    >
      <svg viewBox="0 0 56 56" className="size-full -rotate-90" aria-hidden="true">
        <circle cx="28" cy="28" r={radius} fill="none" strokeWidth="6" className="stroke-(--tone)/15" />
        <circle
          cx="28"
          cy="28"
          r={radius}
          fill="none"
          strokeWidth="6"
          strokeLinecap="butt"
          className="stroke-(--tone)"
          strokeDasharray={circumference}
          strokeDashoffset={circumference * (1 - subject.progress / 100)}
        />
      </svg>
      <span className="absolute inset-0 grid place-items-center font-mono text-xs font-semibold">{subject.progress}%</span>
    </div>
  );
}

export function AcademicProgress({ subjects, featured, totalCount, query }: AcademicProgressProps) {
  const showFeatured = featured && subjects.some((s) => s.id === featured.id);

  return (
    <section id="progress" aria-labelledby="progress-title" className="oc-panel flex h-full scroll-mt-24 flex-col">
      <PanelHeader id="progress-title" title="Progress" tone="cobalt" aside={`${totalCount} courses`} />

      {subjects.length === 0 ? (
        <NoMatches what="courses" />
      ) : (
        <ul className="grid flex-1 grid-cols-2 gap-px bg-line sm:grid-cols-4 lg:grid-cols-2">
          {subjects.map((subject) => (
            <li key={subject.id} style={toneStyle(subject.tone)} className="flex items-center gap-3 bg-surface px-3 py-3.5 sm:px-4">
              <ProgressRing subject={subject} />
              <div className="min-w-0">
                <p className="font-mono text-[0.6875rem] font-medium text-(--tone)">{subject.code}</p>
                <p className="text-sm leading-snug font-medium">
                  <Highlight text={subject.name} query={query} />
                </p>
              </div>
            </li>
          ))}
        </ul>
      )}

      {showFeatured && featured && (
        <div className="mt-auto flex items-center gap-3 border-t border-line bg-accent-soft/70 px-4 py-3 sm:px-5" style={toneStyle(featured.tone)}>
          <div className="min-w-0 flex-1">
            <p className="text-[0.6875rem] font-medium tracking-wide text-ink-subtle uppercase">Up next</p>
            <p className="truncate text-sm font-semibold">
              <Highlight text={featured.nextLesson} query={query} />
            </p>
          </div>
          {/* Lesson content does not exist yet. */}
          <button
            type="button"
            disabled
            aria-label="Continue learning (coming soon)"
            className="inline-flex h-10 shrink-0 cursor-not-allowed items-center gap-1.5 rounded-lg border border-line-strong bg-surface px-3 text-sm font-medium text-ink-subtle"
          >
            Continue <ArrowRight className="size-4" aria-hidden="true" />
          </button>
        </div>
      )}
    </section>
  );
}
