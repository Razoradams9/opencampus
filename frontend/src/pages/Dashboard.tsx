import { CalendarClock, Library, Megaphone, RefreshCw } from "lucide-react";
import { Placeholder } from "../components/Placeholder";
import type { BackendHealth } from "../lib/useBackendHealth";

function greeting(hour: number): string {
  if (hour < 12) return "Good morning";
  if (hour < 18) return "Good afternoon";
  return "Good evening";
}

function formatUptime(seconds: number): string {
  if (seconds < 60) return `${Math.floor(seconds)} s`;
  if (seconds < 3600) return `${Math.floor(seconds / 60)} min`;
  return `${(seconds / 3600).toFixed(1)} h`;
}

export function Dashboard({ health }: { health: BackendHealth }) {
  const now = new Date();
  const today = now.toLocaleDateString(undefined, { weekday: "long", day: "numeric", month: "long" });

  return (
    <div className="space-y-12 lg:space-y-16">
      {/* 01 — Welcome: asymmetric 7/5 split */}
      <section className="grid gap-6 lg:grid-cols-12 lg:gap-8">
        <div className="oc-blueprint relative overflow-hidden border border-line bg-surface px-6 py-8 sm:px-10 sm:py-12 lg:col-span-7">
          <div className="flex items-center justify-between">
            <p className="oc-eyebrow">01 — Overview</p>
            <p className="oc-eyebrow">{today}</p>
          </div>
          <h1 className="mt-10 font-display text-4xl leading-[1.05] font-medium tracking-tight sm:text-5xl">
            {greeting(now.getHours())}.
          </h1>
          <p className="mt-4 max-w-md text-[0.9375rem] leading-relaxed text-ink-muted">
            Welcome to OpenCampus. This is the foundation release: the frame where courses, timetables
            and campus tools will arrive, one milestone at a time.
          </p>
          {/* Signal-colour rule: the one warm accent on the page */}
          <span className="absolute bottom-0 left-6 h-1 w-16 bg-signal sm:left-10" aria-hidden="true" />
        </div>

        <SystemStatus health={health} />
      </section>

      {/* 02 — Workspace placeholders */}
      <section>
        <div className="mb-5 flex items-end justify-between border-b border-line pb-3">
          <h2 className="font-display text-2xl font-medium tracking-tight">Your workspace</h2>
          <p className="oc-eyebrow">02 — Modules</p>
        </div>
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-12">
          <Placeholder
            index="2.1"
            title="Today"
            icon={CalendarClock}
            description="Your classes, office hours and campus events for the day."
            className="lg:col-span-7"
          />
          <Placeholder
            index="2.2"
            title="Announcements"
            icon={Megaphone}
            description="Notices from your institution and faculty."
            className="lg:col-span-5"
          />
          <Placeholder
            index="2.3"
            title="Courses"
            icon={Library}
            description="Courses you teach or are enrolled in, with recent activity."
            className="md:col-span-2 lg:col-span-12"
          />
        </div>
      </section>
    </div>
  );
}

function SystemStatus({ health }: { health: BackendHealth }) {
  const { state, data, error, latencyMs, checkedAt, refresh } = health;

  const headline = {
    checking: { text: "Checking connection…", tone: "text-pending" },
    online: { text: "Connected", tone: "text-success" },
    offline: { text: "Not connected", tone: "text-danger" },
  }[state];

  const rows: [string, string][] = [
    ["Endpoint", "GET /api/health"],
    ["Service", data?.service ?? "—"],
    ["Version", data ? `v${data.version}` : "—"],
    ["Environment", data?.environment ?? "—"],
    ["Latency", latencyMs !== null ? `${latencyMs} ms` : "—"],
    ["Uptime", data ? formatUptime(data.uptime_seconds) : "—"],
    ["Last check", checkedAt ? checkedAt.toLocaleTimeString() : "—"],
  ];

  return (
    <aside className="flex flex-col border border-line bg-surface lg:col-span-5" aria-label="Backend status">
      <header className="flex items-center justify-between border-b border-line px-6 py-4">
        <p className="oc-eyebrow">System status</p>
        <button
          type="button"
          onClick={refresh}
          disabled={state === "checking"}
          className="inline-flex items-center gap-1.5 rounded-oc px-2 py-1 text-xs font-medium text-accent hover:bg-accent-soft disabled:cursor-wait disabled:opacity-60"
        >
          <RefreshCw className={`size-3.5 ${state === "checking" ? "animate-spin" : ""}`} />
          Recheck
        </button>
      </header>

      <div className="px-6 pt-5">
        <p className={`font-display text-2xl font-medium ${headline.tone}`}>{headline.text}</p>
        {state === "offline" && (
          <p className="mt-1 text-sm text-ink-muted">
            {error ?? "Backend unreachable"}. Is the API running on port 8000?
          </p>
        )}
      </div>

      <dl className="mt-4 flex-1 divide-y divide-line px-6 pb-2 text-sm">
        {rows.map(([label, value]) => (
          <div key={label} className="flex justify-between gap-4 py-2">
            <dt className="text-ink-subtle">{label}</dt>
            <dd className="truncate font-mono text-[0.8125rem] text-ink">{value}</dd>
          </div>
        ))}
      </dl>
    </aside>
  );
}
