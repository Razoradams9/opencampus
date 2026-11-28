import { authRequest } from "../auth/session";
import type { Announcement, AnnouncementInput, Course, Coursework, CourseworkInput, Enrolment, FacultyAssignment, LearningResource, ResourceInput, Subject, Submission, TimetableWeek } from "./types";

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

  // ---- Assignments and submissions (M4.5)
  myCoursework: (signal?: AbortSignal) => authRequest<Coursework[]>(`${base}/assignments/me`, { signal }),
  managedCoursework: (signal?: AbortSignal) => authRequest<Coursework[]>(`${base}/assignments/managed?limit=500`, { signal }),
  coursework: (id: string, signal?: AbortSignal) => authRequest<Coursework>(`${base}/assignments/${encodeURIComponent(id)}`, { signal }),
  createCoursework: (subjectId: string, body: CourseworkInput) =>
    authRequest<Coursework>(`${base}/subjects/${encodeURIComponent(subjectId)}/assignments`, { method: "POST", body }),
  updateCoursework: (id: string, body: Partial<CourseworkInput>) =>
    authRequest<Coursework>(`${base}/assignments/${encodeURIComponent(id)}`, { method: "PATCH", body }),
  setCourseworkStatus: (id: string, action: "publish" | "archive") =>
    authRequest<Coursework>(`${base}/assignments/${encodeURIComponent(id)}/${action}`, { method: "POST" }),
  submitWork: (id: string, body: string) =>
    authRequest<Submission>(`${base}/assignments/${encodeURIComponent(id)}/submissions`, { method: "POST", body: { body } }),
  mySubmissions: (id: string, signal?: AbortSignal) =>
    authRequest<Submission[]>(`${base}/assignments/${encodeURIComponent(id)}/submissions/me`, { signal }),
  submissionsFor: (id: string, signal?: AbortSignal) =>
    authRequest<Submission[]>(`${base}/assignments/${encodeURIComponent(id)}/submissions`, { signal }),
  gradeSubmission: (id: string, marks_awarded: number, feedback: string | null) =>
    authRequest<Submission>(`${base}/submissions/${encodeURIComponent(id)}/grades`, { method: "POST", body: { marks_awarded, feedback } }),

  // ---- Announcements (M4.6)
  announcements: (includeExpired: boolean, signal?: AbortSignal) =>
    authRequest<Announcement[]>(`${base}/announcements?limit=200${includeExpired ? "&include_expired=true" : ""}`, { signal }),
  managedAnnouncements: (signal?: AbortSignal) => authRequest<Announcement[]>(`${base}/announcements/managed?limit=200`, { signal }),
  createAnnouncement: (body: AnnouncementInput) => authRequest<Announcement>(`${base}/announcements`, { method: "POST", body }),
  updateAnnouncement: (id: string, body: Partial<AnnouncementInput>) =>
    authRequest<Announcement>(`${base}/announcements/${encodeURIComponent(id)}`, { method: "PATCH", body }),
  setAnnouncementStatus: (id: string, action: "publish" | "archive") =>
    authRequest<Announcement>(`${base}/announcements/${encodeURIComponent(id)}/${action}`, { method: "POST" }),

  week: (scope: "me" | "institution", week: string | null, signal?: AbortSignal) => {
    const path = scope === "me" ? `${base}/timetable/me` : `${base}/timetable`;
    return authRequest<TimetableWeek>(week ? `${path}?week=${week}` : path, { signal });
  },
};
