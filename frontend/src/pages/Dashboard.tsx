import { FlaskConical, X } from "lucide-react";
import { useMemo, useState } from "react";
import { AcademicProgress } from "../components/dashboard/AcademicProgress";
import { AiAssistantTeaser } from "../components/dashboard/AiAssistantTeaser";
import { AssignmentList } from "../components/dashboard/AssignmentList";
import { CampusEventCard } from "../components/dashboard/CampusEventCard";
import { CampusUpdates } from "../components/dashboard/CampusUpdates";
import { QuickActions } from "../components/dashboard/QuickActions";
import { SystemStatus } from "../components/dashboard/SystemStatus";
import { TodaySchedule } from "../components/dashboard/TodaySchedule";
import { WelcomeSection } from "../components/dashboard/WelcomeSection";
import type { DashboardData } from "../data/types";
import { daysBetween } from "../lib/dates";
import { filterDashboard } from "../lib/filterDashboard";
import { subjectLookup } from "../lib/subjects";
import type { BackendHealth } from "../lib/useBackendHealth";

interface DashboardProps {
  data: DashboardData;
  today: Date;
  health: BackendHealth;
  query: string;
  onClearQuery: () => void;
}

export function Dashboard({ data, today, health, query, onClearQuery }: DashboardProps) {
  // Checkbox state is local to this session; nothing is persisted.
  const [assignments, setAssignments] = useState(data.assignments);
  const toggleAssignment = (id: string) =>
    setAssignments((list) => list.map((a) => (a.id === id ? { ...a, done: !a.done } : a)));

  const subjects = useMemo(() => subjectLookup(data.subjects), [data.subjects]);
  const filtered = filterDashboard(data, assignments, query);
  const searching = query.trim() !== "";

  const dueThisWeek = assignments.filter((a) => {
    const days = daysBetween(today, a.due);
    return !a.done && days >= 0 && days <= 7;
  }).length;
  const featured = data.subjects.find((s) => s.progress < 100);

  return (
    <div className="space-y-6 lg:space-y-8">
      {searching ? (
        <div
          role="status"
          className="flex items-center justify-between gap-3 border border-accent/30 bg-accent-soft px-4 py-2.5 text-sm"
        >
          <p>
            <span className="font-semibold">{filtered.total}</span> {filtered.total === 1 ? "match" : "matches"} for
            “<span className="font-medium">{query.trim()}</span>” on this dashboard
          </p>
          <button
            type="button"
            onClick={onClearQuery}
            className="inline-flex items-center gap-1 rounded-oc px-2 py-1 text-xs font-medium text-accent hover:bg-surface"
          >
            <X className="size-3.5" aria-hidden="true" /> Clear
          </button>
        </div>
      ) : (
        <p className="flex items-center gap-2 text-xs text-ink-subtle">
          <FlaskConical className="size-3.5 shrink-0" aria-hidden="true" />
          Demonstration data: the student, college and courses shown are fictional.
        </p>
      )}

      {!searching && (
        <>
          <div className="grid gap-6 lg:grid-cols-12 lg:gap-8">
            <div className="lg:col-span-8 *:h-full">
              <WelcomeSection
                student={data.student}
                today={today}
                classesToday={data.schedule.length}
                dueThisWeek={dueThisWeek}
              />
            </div>
            <div className="lg:col-span-4 *:h-full">
              <AiAssistantTeaser />
            </div>
          </div>
          <QuickActions />
        </>
      )}

      <div className="grid gap-6 lg:grid-cols-12 lg:gap-8">
        <div className="lg:col-span-7 *:h-full">
          <AcademicProgress subjects={filtered.subjects} featured={featured} totalCount={data.subjects.length} query={query} />
        </div>
        <div className="lg:col-span-5 *:h-full">
          <TodaySchedule items={filtered.schedule} subjects={subjects} now={new Date()} totalCount={data.schedule.length} query={query} />
        </div>
      </div>

      <div className="grid gap-6 lg:grid-cols-12 lg:gap-8">
        <div className="lg:col-span-7 *:h-full">
          <AssignmentList
            assignments={filtered.assignments}
            allAssignments={assignments}
            subjects={subjects}
            today={today}
            query={query}
            onToggle={toggleAssignment}
          />
        </div>
        <div className="lg:col-span-5 *:h-full">
          <CampusUpdates updates={filtered.updates} today={today} query={query} />
        </div>
      </div>

      <div className="grid gap-6 lg:grid-cols-12 lg:gap-8">
        {filtered.eventMatches && (
          <div className="lg:col-span-8 *:h-full">
            <CampusEventCard event={data.event} today={today} query={query} />
          </div>
        )}
        {!searching && (
          <div className="lg:col-span-4 *:h-full">
            <SystemStatus health={health} />
          </div>
        )}
      </div>
    </div>
  );
}
