/**
 * Demonstration academic content. Every course, class and person here is fictional.
 * The signed-in user and institution are real (from auth); this content is not.
 * Dates are generated relative to "today" so the demo always looks current.
 * Replace this module with API calls when the backend provides real data.
 */
import { addDays } from "../lib/dates";
import type { DashboardData } from "./types";

export function createDemoDashboard(today: Date = new Date()): DashboardData {
  const day = (offset: number) => addDays(today, offset);

  return {
    subjects: [
      {
        id: "cs201",
        code: "CS201",
        name: "Data Structures",
        tone: "cobalt",
        progress: 68,
        lessonsCompleted: 8,
        lessonsTotal: 12,
        nextLesson: "Lesson 9 · Binary heaps",
      },
      {
        id: "cs214",
        code: "CS214",
        name: "Discrete Mathematics",
        tone: "teal",
        progress: 54,
        lessonsCompleted: 7,
        lessonsTotal: 13,
        nextLesson: "Lesson 8 · Graph colouring",
      },
      {
        id: "cs230",
        code: "CS230",
        name: "Computer Architecture",
        tone: "amber",
        progress: 41,
        lessonsCompleted: 5,
        lessonsTotal: 12,
        nextLesson: "Lesson 6 · Pipeline hazards",
      },
      {
        id: "hum110",
        code: "HUM110",
        name: "Technical Writing",
        tone: "rose",
        progress: 82,
        lessonsCompleted: 9,
        lessonsTotal: 11,
        nextLesson: "Lesson 10 · Editing for clarity",
      },
    ],

    schedule: [
      { id: "s1", subjectId: "cs201", kind: "Lecture", start: "09:00", end: "10:30", room: "B-204", building: "Hall of Engineering", instructor: "Dr. Lena Varga" },
      { id: "s2", subjectId: "cs214", kind: "Tutorial", start: "11:00", end: "12:00", room: "C-112", building: "Mathematics Building", instructor: "Prof. Samuel Achebe" },
      { id: "s3", subjectId: "cs230", kind: "Lab", start: "13:30", end: "15:00", room: "Lab 3", building: "West Wing", instructor: "Dr. Priya Raman" },
      { id: "s4", subjectId: "hum110", kind: "Seminar", start: "16:00", end: "17:00", room: "L2 Study Room", building: "Central Library", instructor: "Ms. Clara Holm" },
    ],

    assignments: [
      { id: "a1", subjectId: "cs201", title: "Problem set 4: heap implementation", due: day(1), priority: "high", done: false },
      { id: "a2", subjectId: "cs230", title: "Pre-lab questions for Lab 4", due: day(0), priority: "medium", done: false },
      { id: "a3", subjectId: "hum110", title: "Peer review of process document", due: day(2), priority: "low", done: true },
      { id: "a4", subjectId: "cs214", title: "Graph theory worksheet", due: day(3), priority: "medium", done: false },
      { id: "a5", subjectId: "cs230", title: "Pipeline simulator report", due: day(6), priority: "high", done: false },
    ],

    updates: [
      { id: "u1", title: "Mid-semester course feedback is open", body: "Share feedback on each of your courses before the window closes next Friday.", category: "Academic", date: day(-1), important: true },
      { id: "u2", title: "Wi-Fi maintenance in the North Block", body: "Expect intermittent connectivity on Saturday between 07:00 and 10:00.", category: "IT", date: day(-2), important: true },
      { id: "u3", title: "Library extends evening hours", body: "The Central Library stays open until 23:00 throughout the exam period.", category: "Facilities", date: day(0), important: false },
      { id: "u4", title: "Societies fair: stall applications", body: "Student societies can apply for a stall at next month's fair.", category: "Campus life", date: day(-4), important: false },
    ],

    event: {
      id: "e1",
      title: "Open Lab Night",
      summary: "Student teams demo their semester projects across robotics, systems and design. Open to all years.",
      date: day(9),
      start: "18:00",
      end: "21:00",
      location: "Engineering Atrium",
      host: "School of Computing",
    },
  };
}
