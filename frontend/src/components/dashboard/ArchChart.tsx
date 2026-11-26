import type React from "react";
import type { Subject } from "../../data/types";

/**
 * Semester progress as concentric arches (the OpenCampus mark, made useful):
 * one arc per course, its length is the share of the course completed.
 * The centre shows the average. Arcs fill once on entrance.
 */
export function ArchChart({ subjects }: { subjects: Subject[] }) {
  const cx = 130;
  const cy = 124;
  const outer = 114;
  const step = 16;
  const stroke = 10;
  const average = subjects.length ? Math.round(subjects.reduce((sum, s) => sum + s.progress, 0) / subjects.length) : 0;

  return (
    <figure className="relative mx-auto w-full max-w-[19rem] pb-5">
      <svg viewBox="0 0 260 132" className="w-full" role="img" aria-label={`Average progress ${average} percent across ${subjects.length} courses`}>
        {subjects.map((subject, i) => {
          const r = outer - i * step;
          const d = `M ${cx - r} ${cy} A ${r} ${r} 0 0 1 ${cx + r} ${cy}`;
          const p = subject.progress / 100;
          return (
            <g key={subject.id}>
              <path d={d} fill="none" stroke="white" strokeOpacity="0.7" strokeWidth={stroke} strokeLinecap="round" />
              <path
                d={d}
                pathLength={1}
                fill="none"
                stroke={`var(--oc-subject-${subject.tone})`}
                strokeWidth={stroke}
                strokeLinecap="round"
                strokeDasharray={`${p} 1`}
                className="oc-arc"
                style={{ "--p": p, "--i": i } as React.CSSProperties}
              />
            </g>
          );
        })}
      </svg>
      {/* Numeral sits inside the innermost arch; its label sits below the baseline. */}
      <span className="absolute inset-x-0 bottom-5 text-center font-display text-[2.5rem] leading-none font-medium tabular-nums" aria-hidden="true">
        {average}
        <span className="text-lg text-ink-muted">%</span>
      </span>
      <figcaption className="absolute inset-x-0 bottom-0 text-center font-mono text-[0.6875rem] text-ink-muted" aria-hidden="true">
        average across {subjects.length} courses
      </figcaption>
    </figure>
  );
}
