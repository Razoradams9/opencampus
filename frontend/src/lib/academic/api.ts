import { authRequest } from "../auth/session";
import type { Course, Enrolment, FacultyAssignment, Subject, TimetableWeek } from "./types";

const base = "/api/academic";

export const academicApi = {
  courses: (signal?: AbortSignal) => authRequest<Course[]>(`${base}/courses`, { signal }),
  subjects: (courseId: string, signal?: AbortSignal) =>
    authRequest<Subject[]>(`${base}/courses/${encodeURIComponent(courseId)}/subjects`, { signal }),
  myEnrolments: (signal?: AbortSignal) => authRequest<Enrolment[]>(`${base}/enrolments/me`, { signal }),
  myAssignments: (signal?: AbortSignal) =>
    authRequest<FacultyAssignment[]>(`${base}/faculty-assignments/me?status=active`, { signal }),
  /** Personal week (taught or attended), or the whole institution's for admins. */
  week: (scope: "me" | "institution", week: string | null, signal?: AbortSignal) => {
    const path = scope === "me" ? `${base}/timetable/me` : `${base}/timetable`;
    return authRequest<TimetableWeek>(week ? `${path}?week=${week}` : path, { signal });
  },
};
