import type { Coursework } from "./types";

export type Bucket = "due" | "overdue" | "submitted" | "graded";

/** Where an assignment sits for the signed-in student. */
export function bucketOf(a: Coursework): Bucket {
  if (a.me?.status === "graded") return "graded";
  if (a.me?.status === "submitted") return "submitted";
  return a.window === "open" ? "due" : "overdue";
}

export function relativeDeadline(dueIso: string, now = new Date()): string {
  const ms = new Date(dueIso).getTime() - now.getTime();
  const abs = Math.abs(ms);
  const hours = Math.round(abs / 3_600_000);
  const days = Math.round(abs / 86_400_000);
  const span = abs < 3_600_000 ? "under an hour" : hours < 36 ? `${hours} hour${hours === 1 ? "" : "s"}` : `${days} day${days === 1 ? "" : "s"}`;
  return ms >= 0 ? `Due in ${span}` : `Overdue by ${span}`;
}

/** Share of the working window already used, 0–1 (for the deadline bar). */
export function elapsed(a: Coursework, now = new Date()): number {
  const start = new Date(a.available_from).getTime();
  const end = new Date(a.due_at).getTime();
  return Math.min(1, Math.max(0, (now.getTime() - start) / (end - start)));
}

export function formatDateTime(iso: string): string {
  return new Date(iso).toLocaleString(undefined, { weekday: "short", day: "numeric", month: "short", hour: "numeric", minute: "2-digit" });
}

/** ISO → value for <input type="datetime-local"> in the browser's zone. */
export function toLocalInput(iso: string | null): string {
  if (!iso) return "";
  const d = new Date(iso);
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

/** <input type="datetime-local"> value (local wall time) → ISO with offset. */
export function fromLocalInput(value: string): string {
  return new Date(value).toISOString();
}

export const LATE_POLICY_TEXT = {
  reject: "No submissions after the deadline.",
  accept: "Late submissions are accepted and marked late.",
  accept_until: "Late submissions are accepted, marked late, until the cut-off.",
} as const;
