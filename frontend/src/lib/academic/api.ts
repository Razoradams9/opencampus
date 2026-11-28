import { authRequest } from "../auth/session";
import type { Course, Enrolment, FacultyAssignment, LearningResource, ResourceInput, Subject, TimetableWeek } from "./types";

const base = "/api/academic";

export const academicApi = {
  courses: (signal?: AbortSignal) => authRequest<Course[]>(`${base}/courses`, { signal }),
  subjects: (courseId: string, signal?: AbortSignal) =>
    authRequest<Subject[]>(`${base}/courses/${encodeURIComponent(courseId)}/subjects`, { signal }),
  myEnrolments: (signal?: AbortSignal) => authRequest<Enrolment[]>(`${base}/enrolments/me`, { signal }),
  myAssignments: (signal?: AbortSignal) =>
    authRequest<FacultyAssignment[]>(`${base}/faculty-assignments/me?status=active`, { signal }),
  /** Personal week (taught or attended), or the whole institution's for admins. */
  allSubjectsFor: async (courses: Course[], signal?: AbortSignal) =>
    (await Promise.all(courses.map((c) => academicApi.subjects(c.id, signal).then((list) => list.map((s) => ({ s, c })))))).flat(),

  // ---- Learning resources (M4.4)
  availableResources: (signal?: AbortSignal) => authRequest<LearningResource[]>(`${base}/resources/me`, { signal }),
  managedResources: (signal?: AbortSignal) => authRequest<LearningResource[]>(`${base}/resources/managed?limit=500`, { signal }),
  createResource: (subjectId: string, body: ResourceInput) =>
    authRequest<LearningResource>(`${base}/subjects/${encodeURIComponent(subjectId)}/resources`, { method: "POST", body }),
  updateResource: (id: string, body: Partial<ResourceInput>) =>
    authRequest<LearningResource>(`${base}/resources/${encodeURIComponent(id)}`, { method: "PATCH", body }),
  setResourceStatus: (id: string, action: "publish" | "archive") =>
    authRequest<LearningResource>(`${base}/resources/${encodeURIComponent(id)}/${action}`, { method: "POST" }),

  week: (scope: "me" | "institution", week: string | null, signal?: AbortSignal) => {
    const path = scope === "me" ? `${base}/timetable/me` : `${base}/timetable`;
    return authRequest<TimetableWeek>(week ? `${path}?week=${week}` : path, { signal });
  },
};
