import type { Role } from "../auth/types";
import { academicApi } from "./api";
import type { MySubject } from "./types";

/**
 * Subjects relevant to the signed-in member, by role: students get subjects
 * of their active enrolments' courses, faculty the subjects they are assigned
 * to, admins every active subject. The backend enforces access either way;
 * this only decides what to offer in the UI.
 */
export async function loadMySubjects(role: Role, signal?: AbortSignal): Promise<MySubject[]> {
  let list: MySubject[];
  if (role === "faculty") {
    const assignments = await academicApi.myAssignments(signal);
    list = assignments.map((a) => ({ subject: a.subject, course: a.course }));
  } else if (role === "student") {
    const enrolments = (await academicApi.myEnrolments(signal)).filter((e) => e.status === "active");
    const courses = [...new Map(enrolments.map((e) => [e.course.id, e.course])).values()];
    const subjects = await Promise.all(courses.map((c) => academicApi.subjects(c.id, signal).then((s) => s.map((x) => ({ x, c })))));
    list = subjects.flat().map(({ x, c }) => ({ subject: x, course: c }));
  } else {
    const courses = await academicApi.courses(signal);
    const pairs = await academicApi.allSubjectsFor(courses.filter((c) => c.status === "active"), signal);
    list = pairs.filter(({ s }) => s.status === "active").map(({ s, c }) => ({ subject: s, course: c }));
  }
  const unique = new Map(list.map((item) => [item.subject.id, item]));
  return [...unique.values()].sort((a, b) => a.course.code.localeCompare(b.course.code) || a.subject.semester - b.subject.semester || a.subject.code.localeCompare(b.subject.code));
}
