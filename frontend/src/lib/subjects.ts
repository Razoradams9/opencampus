import type { CSSProperties } from "react";
import type { Subject, SubjectTone } from "../data/types";

/** Exposes a subject's colour token as --tone for use in Tailwind arbitrary values. */
export function toneStyle(tone: SubjectTone): CSSProperties {
  return { "--tone": `var(--oc-subject-${tone})` } as CSSProperties;
}

export function subjectLookup(subjects: Subject[]): Map<string, Subject> {
  return new Map(subjects.map((subject) => [subject.id, subject]));
}
