import { ClipboardCheck } from "lucide-react";
import { ManageCoursework } from "../components/coursework/ManageCoursework";
import { StudentCoursework } from "../components/coursework/StudentCoursework";
import type { ActiveInstitution } from "../lib/auth/types";
import { useLocation } from "../lib/router";

/** Assignments: students submit and see grades; faculty set work and grade it. */
export function CourseworkPage({ institution }: { institution: ActiveInstitution }) {
  const { search } = useLocation();
  const id = new URLSearchParams(search).get("id");
  const student = institution.role === "student";
  return (
    <div className="space-y-6">
      {!id && (
        <header className="flex items-start gap-4">
          <ClipboardCheck className="mt-1 size-7 shrink-0 text-subject-rose" aria-hidden="true" />
          <div>
            <p className="oc-eyebrow">{student ? "Your coursework" : "Set and grade work"}</p>
            <h1 className="font-display text-[2.25rem] leading-none font-medium tracking-tight sm:text-[2.75rem]">Assignments</h1>
          </div>
        </header>
      )}
      {student ? <StudentCoursework id={id} /> : <ManageCoursework id={id} role={institution.role} />}
    </div>
  );
}
