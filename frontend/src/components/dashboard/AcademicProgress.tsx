import type { Subject } from "../../data/types";
import { toneStyle } from "../../lib/subjects";
import { Highlight } from "../ui/Highlight";
import { NoMatches } from "../ui/NoMatches";
import { SectionHeading } from "../ui/SectionHeading";
import { SubjectMark } from "../ui/SubjectMark";

interface AcademicProgressProps {
  subjects: Subject[];
  totalCount: number;
  query: string;
}

/** One segment per lesson: completed lessons filled in the subject colour. */
function LessonTrack({ subject }: { subject: Subject }) {
  return (
    <div
      role="progressbar"
      aria-valuenow={subject.lessonsCompleted}
      aria-valuemin={0}
      aria-valuemax={subject.lessonsTotal}
      aria-label={`${subject.name}: ${subject.lessonsCompleted} of ${subject.lessonsTotal} lessons`}
      className="flex gap-[3px]"
    >
      {Array.from({ length: subject.lessonsTotal }, (_, i) => (
        <span key={i} className={`h-2.5 flex-1 rounded-[2px] ${i < subject.lessonsCompleted ? "bg-(--tone)" : "bg-white/70"}`} />
      ))}
    </div>
  );
}

/** Progress sits on its own sage colour block, not a white card. */
export function AcademicProgress({ subjects, totalCount, query }: AcademicProgressProps) {
  return (
    <section id="progress" aria-labelledby="progress-title" className="flex h-full scroll-mt-24 flex-col">
      <SectionHeading id="progress-title" title="Progress" accent="var(--oc-subject-cobalt)" meta={`${totalCount} courses`} />

      <div className="flex flex-1 flex-col rounded-card bg-lavender p-4 shadow-e1 sm:p-5">
        {subjects.length === 0 ? (
          <NoMatches what="courses" />
        ) : (
          <ul className="space-y-4">
            {subjects.map((subject) => (
              <li key={subject.id} style={toneStyle(subject.tone)}>
                <div className="mb-1.5 flex items-end justify-between gap-3">
                  <p className="flex min-w-0 items-center gap-2">
                    <SubjectMark tone={subject.tone} className="size-3" />
                    <span className="font-mono text-[0.6875rem] font-medium text-ink-muted">{subject.code}</span>
                    <span className="truncate text-[0.9375rem] font-semibold">
                      <Highlight text={subject.name} query={query} />
                    </span>
                  </p>
                  <p className="shrink-0 font-display text-2xl leading-none font-medium tabular-nums">
                    {subject.progress}
                    <span className="text-sm text-ink-muted">%</span>
                  </p>
                </div>
                <LessonTrack subject={subject} />
              </li>
            ))}
          </ul>
        )}
      </div>
    </section>
  );
}
