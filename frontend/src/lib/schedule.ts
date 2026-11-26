import type { ScheduleItem } from "../data/types";
import { toMinutes } from "./dates";

export type SlotState = "past" | "now" | "next" | "later";

/** Classifies each class relative to the current time. */
export function slotStates(items: ScheduleItem[], now: Date): Map<string, SlotState> {
  const minutes = now.getHours() * 60 + now.getMinutes();
  const states = new Map<string, SlotState>();
  let nextAssigned = false;
  for (const item of [...items].sort((a, b) => toMinutes(a.start) - toMinutes(b.start))) {
    if (toMinutes(item.end) <= minutes) states.set(item.id, "past");
    else if (toMinutes(item.start) <= minutes) states.set(item.id, "now");
    else if (!nextAssigned) {
      states.set(item.id, "next");
      nextAssigned = true;
    } else states.set(item.id, "later");
  }
  return states;
}

/** The class in progress, else the next one today, else undefined. */
export function currentOrNextClass(items: ScheduleItem[], now: Date): { item: ScheduleItem; state: "now" | "next" } | undefined {
  const states = slotStates(items, now);
  const current = items.find((i) => states.get(i.id) === "now");
  if (current) return { item: current, state: "now" };
  const next = items.find((i) => states.get(i.id) === "next");
  return next ? { item: next, state: "next" } : undefined;
}

/** "in 25 min", "in 1 h 5 min": time until `target` ("HH:MM") from `now`. */
export function minutesUntil(target: string, now: Date): number {
  return toMinutes(target) - (now.getHours() * 60 + now.getMinutes());
}

export function formatDuration(minutes: number): string {
  if (minutes < 1) return "under a minute";
  if (minutes < 60) return `${minutes} min`;
  const h = Math.floor(minutes / 60);
  const m = minutes % 60;
  return m ? `${h} h ${m} min` : `${h} h`;
}
