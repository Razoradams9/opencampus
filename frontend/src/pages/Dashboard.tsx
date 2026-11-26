import { X } from "lucide-react";
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
import type { ActiveInstitution, AuthUser } from "../lib/auth/types";
import { filterDashboard } from "../lib/filterDashboard";
import { currentOrNextClass } from "../lib/schedule";
import { subjectLookup } from "../lib/subjects";
import type { BackendHealth } from "../lib/useBackendHealth";

interface DashboardProps {
  user: AuthUser;
  institution: ActiveInstitution;
  data: DashboardData;
  today: Date;
  health: BackendHealth;
  query: string;
  onClearQuery: () => void;
}

/**
 * One grid for every screen size. Source order is the phone order (what a
 * student checks first: next class, then what's due); on desktop, `lg:order`
 * and column spans arrange the same blocks into two columns.
 */
export function Dashboard({ user, institution, data, today, health, query, onClearQuery }: DashboardProps) {
  // Checkbox state is local to this session; nothing is persisted.
  const [assignments, setAssignments] = useState(data.assignments);
  const toggleAssignment = (id: string) =>
    setAssignments((list) => list.map((a) => (a.id === id ? { ...a, done: !a.done } : a)));

  const now = new Date();
  const subjects = useMemo(() => subjectLookup(data.subjects), [data.subjects]);
  const filtered = filterDashboard(data, assignments, query);
  const searching = query.trim() !== "";
  const upcoming = currentOrNextClass(data.schedule, now);

  const tasksDone = assignments.filter((a) => a.done).length;
  const featured = data.subjects.find((s) => s.progress < 100);

  return (
    <div className="space-y-4">
      {searching && (
        <div role="status" className="flex items-center justify-between gap-3 rounded-xl bg-accent-soft px-4 py-2.5 text-sm shadow-e1">
          <p>
            <span className="font-semibold">{filtered.total}</span> {filtered.total === 1 ? "match" : "matches"} for “
            <span className="font-medium">{query.trim()}</span>”
          </p>
          <button
            type="button"
            onClick={onClearQuery}
            className="inline-flex h-9 items-center gap-1 rounded-oc px-2 text-xs font-medium text-accent hover:bg-surface"
          >
            <X className="size-3.5" aria-hidden="true" /> Clear
          </button>
        </div>
      )}

      <div className="grid grid-cols-[minmax(0,1fr)] gap-x-4 gap-y-8 lg:grid-cols-12 lg:gap-x-8 lg:gap-y-10">
        {!searching && (
          <div className="lg:order-1 lg:col-span-8">
            <WelcomeSection
              firstName={user.full_name.split(" ")[0]}
              institutionName={institution.name}
              today={today}
              now={now}
              schedule={data.schedule}
              subjects={subjects}
              upcoming={upcoming}
              tasksDone={tasksDone}
              tasksTotal={assignments.length}
            />
          </div>
        )}
        {!searching && (
          <div className="lg:order-3 lg:col-span-12">
            <QuickActions />
          </div>
        )}
        <div className="lg:order-4 lg:col-span-5">
          <TodaySchedule items={filtered.schedule} subjects={subjects} now={now} totalCount={data.schedule.length} query={query} />
        </div>
        <div className="lg:order-5 lg:col-span-7">
          <AssignmentList
            searching={searching}
            assignments={filtered.assignments}
            allAssignments={assignments}
            subjects={subjects}
            today={today}
            query={query}
            onToggle={toggleAssignment}
          />
        </div>
        <div className="lg:order-6 lg:col-span-7">
          <AcademicProgress subjects={filtered.subjects} featured={featured} totalCount={data.subjects.length} query={query} />
        </div>
        <div className="lg:order-7 lg:col-span-5">
          <CampusUpdates updates={filtered.updates} today={today} query={query} />
        </div>
        {filtered.eventMatches && (
          <div className="lg:order-8 lg:col-span-8">
            <CampusEventCard event={data.event} today={today} query={query} />
          </div>
        )}
        {!searching && (
          <div className="lg:order-2 lg:col-span-4">
            <AiAssistantTeaser />
          </div>
        )}
        {/* Developer diagnostics: not shown to students in production builds. */}
        {import.meta.env.DEV && !searching && (
          <div className="lg:order-9 lg:col-span-4">
            <SystemStatus health={health} />
          </div>
        )}
      </div>
    </div>
  );
}
