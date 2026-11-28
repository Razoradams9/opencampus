/** Mirrors the backend's /api/academic response schemas (M4). */
export type { Role } from "../auth/types";
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

export type PublicationStatus = "draft" | "published" | "archived";
export type ResourceType = "pdf" | "document" | "presentation" | "video" | "link" | "note";

export interface LearningResource {
  id: string;
  course: CourseRef;
  subject: SubjectRef;
  title: string;
  description: string | null;
  resource_type: ResourceType;
  topic: string | null;
  body: string | null;
  external_url: string | null;
  file_available: boolean;
  status: PublicationStatus;
  created_by: TeacherRef;
  published_at: string | null;
  updated_at: string;
}

export interface ResourceInput {
  title: string;
  description: string | null;
  resource_type: ResourceType;
  topic: string | null;
  body: string | null;
  external_url: string | null;
}

/** A subject the signed-in member studies or teaches, with its course. */
export interface MySubject {
  subject: SubjectRef;
  course: CourseRef;
}

export type LatePolicy = "reject" | "accept" | "accept_until";
export type SubmissionWindow = "not_open" | "open" | "late" | "closed";

export interface Grade {
  marks_awarded: number;
  feedback: string | null;
  graded_at: string;
  graded_by: TeacherRef;
}

export interface Coursework {
  id: string;
  course: CourseRef;
  subject: SubjectRef;
  title: string;
  instructions: string;
  reference_url: string | null;
  available_from: string;
  due_at: string;
  late_policy: LatePolicy;
  late_cutoff_at: string | null;
  max_marks: number;
  status: PublicationStatus;
  published_at: string | null;
  created_by: TeacherRef;
  window: SubmissionWindow;
  me: { status: "not_submitted" | "submitted" | "graded"; attempts: number; last_submitted_at: string | null; is_late: boolean; grade: Grade | null } | null;
  submitted_students: number | null;
  graded_students: number | null;
}

export interface CourseworkInput {
  title: string;
  instructions: string;
  reference_url: string | null;
  available_from: string;
  due_at: string;
  late_policy: LatePolicy;
  late_cutoff_at: string | null;
  max_marks: number;
}

export interface Submission {
  id: string;
  assignment_id: string;
  student: { membership_id: string; full_name: string; email: string };
  attempt: number;
  body: string | null;
  submitted_at: string;
  is_late: boolean;
  status: "submitted" | "graded" | "superseded";
  grade: Grade | null;
  grade_history: Grade[];
}
