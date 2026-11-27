import type { SubjectTone } from "../../data/types";

const TONES: SubjectTone[] = ["cobalt", "teal", "amber", "rose", "violet"];

/** Stable colour (and shape) per subject code, so a subject reads the same everywhere. */
export function toneFor(code: string): SubjectTone {
  let hash = 0;
  for (const char of code) hash = (hash * 31 + char.charCodeAt(0)) >>> 0;
  return TONES[hash % TONES.length];
}

/** YYYY-MM-DD of an instant, as a calendar date in `timeZone`. */
export function dateKey(iso: string, timeZone: string): string {
  const parts = new Intl.DateTimeFormat("en-CA", { timeZone, year: "numeric", month: "2-digit", day: "2-digit" }).formatToParts(
    new Date(iso),
  );
  const get = (type: string) => parts.find((p) => p.type === type)?.value ?? "";
  return `${get("year")}-${get("month")}-${get("day")}`;
}

export function formatClock(iso: string, timeZone: string): string {
  return new Date(iso).toLocaleTimeString(undefined, { timeZone, hour: "numeric", minute: "2-digit" });
}

/** Add days to a YYYY-MM-DD date (pure calendar arithmetic, no timezone). */
export function addDaysKey(key: string, days: number): string {
  const [y, m, d] = key.split("-").map(Number);
  const date = new Date(Date.UTC(y, m - 1, d + days));
  return date.toISOString().slice(0, 10);
}

export function formatDayKey(key: string, options: Intl.DateTimeFormatOptions): string {
  const [y, m, d] = key.split("-").map(Number);
  return new Date(Date.UTC(y, m - 1, d)).toLocaleDateString(undefined, { timeZone: "UTC", ...options });
}
