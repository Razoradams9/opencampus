/** Types for the student dashboard. Shaped so a future API can return them as-is. */

export type SubjectTone = "cobalt" | "teal" | "amber" | "rose";

export interface StudentProfile {
  firstName: string;
  fullName: string;
  initials: string;
  programme: string;
  year: string;
}

export interface College {
  name: string;
  campus: string;
}

export interface Subject {
  id: string;
  code: string;
  name: string;
  tone: SubjectTone;
  /** Completed share of the course, 0–100. */
  progress: number;
  lessonsCompleted: number;
  lessonsTotal: number;
  nextLesson: string;
}

export type ClassKind = "Lecture" | "Tutorial" | "Lab" | "Seminar";

export interface ScheduleItem {
  id: string;
  subjectId: string;
  kind: ClassKind;
  /** 24h local time, "HH:MM". */
  start: string;
  end: string;
  room: string;
  building: string;
  instructor: string;
}

export type Priority = "high" | "medium" | "low";

export interface Assignment {
  id: string;
  subjectId: string;
  title: string;
  due: Date;
  priority: Priority;
  done: boolean;
}

export type UpdateCategory = "Academic" | "Facilities" | "IT" | "Campus life";

export interface CampusUpdate {
  id: string;
  title: string;
  body: string;
  category: UpdateCategory;
  date: Date;
  important: boolean;
}

export interface CampusEvent {
  id: string;
  title: string;
  summary: string;
  date: Date;
  start: string;
  end: string;
  location: string;
  host: string;
}

export interface DashboardData {
  student: StudentProfile;
  college: College;
  subjects: Subject[];
  schedule: ScheduleItem[];
  assignments: Assignment[];
  updates: CampusUpdate[];
  event: CampusEvent;
}
