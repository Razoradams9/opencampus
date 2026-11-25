import type { Assignment, DashboardData, ScheduleItem, Subject, CampusUpdate } from "../data/types";
import { matches } from "./search";

export interface FilteredDashboard {
  subjects: Subject[];
  schedule: ScheduleItem[];
  assignments: Assignment[];
  updates: CampusUpdate[];
  eventMatches: boolean;
  total: number;
}

/** Filters the dashboard's visible sample content by a free-text query. */
export function filterDashboard(
  data: DashboardData,
  assignments: Assignment[],
  query: string,
): FilteredDashboard {
  const subjectById = new Map(data.subjects.map((s) => [s.id, s]));
  const subjectText = (id: string) => {
    const s = subjectById.get(id);
    return s ? `${s.code} ${s.name}` : "";
  };

  const subjects = data.subjects.filter((s) => matches(query, s.code, s.name, s.nextLesson));
  // Only fields that are visible on screen are searched.
  const schedule = data.schedule.filter((c) => matches(query, subjectText(c.subjectId), c.kind, c.room));
  const filteredAssignments = assignments.filter((a) => matches(query, a.title, subjectText(a.subjectId)));
  const updates = data.updates.filter((u) => matches(query, u.title, u.category));
  const e = data.event;
  const eventMatches = matches(query, e.title, e.summary, e.location);

  return {
    subjects,
    schedule,
    assignments: filteredAssignments,
    updates,
    eventMatches,
    total:
      subjects.length + schedule.length + filteredAssignments.length + updates.length + (eventMatches ? 1 : 0),
  };
}
