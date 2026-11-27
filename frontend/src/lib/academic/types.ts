/** Mirrors the backend's /api/academic response schemas (M4). */
export type RecordStatus = "active" | "archived";
export type DegreeLevel = "certificate" | "diploma" | "associate" | "bachelor" | "master" | "doctorate" | "other";
export type EnrolmentStatus = "active" | "suspended" | "withdrawn" | "completed";
export type SessionStatus = "scheduled" | "cancelled";

export interface Course {
  id: string;
  name: string;
  code: string;
  description: string | null;
  degree_level: DegreeLevel;
  duration_semesters: number;
  status: RecordStatus;
}

export interface CourseRef {
  id: string;
  name: string;
  code: string;
  status: RecordStatus;
}

export interface Subject {
  id: string;
  course_id: string;
  name: string;
  code: string;
  description: string | null;
  semester: number;
  credits: number;
  status: RecordStatus;
}

export interface SubjectRef {
  id: string;
  name: string;
  code: string;
  semester: number;
  credits: number;
}

export interface Enrolment {
  id: string;
  student: { membership_id: string; user_id: string; full_name: string; email: string };
  course: CourseRef;
  academic_year: string;
  academic_period: string;
  status: EnrolmentStatus;
  enrolled_at: string;
}

export interface TeacherRef {
  membership_id: string;
  full_name: string;
}

export interface FacultyAssignment {
  id: string;
  course: CourseRef;
  subject: SubjectRef;
  faculty: TeacherRef;
  academic_year: string;
  academic_period: string;
  status: "active" | "ended";
}

export interface ClassSession {
  id: string;
  /** UTC ISO timestamps. Display in the timetable's timezone. */
  start_at: string;
  end_at: string;
  status: SessionStatus;
  course: CourseRef;
  subject: SubjectRef;
  faculty: TeacherRef;
  room: { id: string; name: string; building: string } | null;
  academic_year: string;
  academic_period: string;
}

export interface TimetableWeek {
  timezone: string;
  week_start: string; // YYYY-MM-DD (Monday)
  week_end: string;
  starts_at: string;
  ends_at: string;
  sessions: ClassSession[];
}

export const DEGREE_LABEL: Record<DegreeLevel, string> = {
  certificate: "Certificate",
  diploma: "Diploma",
  associate: "Associate",
  bachelor: "Bachelor's",
  master: "Master's",
  doctorate: "Doctorate",
  other: "Programme",
};
