import type { SubjectTone } from "../../data/types";

/**
 * Each subject tone has its own shape as well as its colour, so subjects
 * stay distinguishable without relying on colour alone.
 */
const SHAPES: Record<SubjectTone, string> = {
  cobalt: "M8 1.5a6.5 6.5 0 1 1 0 13 6.5 6.5 0 0 1 0-13Z", // circle
  teal: "M2 2h12v12H2Z", // square
  amber: "M8 1.5 14.5 14h-13Z", // triangle
  rose: "M8 1 15 8l-7 7-7-7Z", // diamond
  violet: "M8 1l6 3.5v7L8 15l-6-3.5v-7Z", // hexagon
};

interface SubjectMarkProps {
  tone: SubjectTone;
  className?: string;
  hollow?: boolean;
}

export function SubjectMark({ tone, className = "size-3", hollow = false }: SubjectMarkProps) {
  return (
    <svg viewBox="0 0 16 16" className={`shrink-0 ${className}`} aria-hidden="true">
      <path
        d={SHAPES[tone]}
        fill={hollow ? "none" : `var(--oc-subject-${tone})`}
        stroke={`var(--oc-subject-${tone})`}
        strokeWidth={hollow ? 2 : 0}
        strokeLinejoin="round"
      />
    </svg>
  );
}
