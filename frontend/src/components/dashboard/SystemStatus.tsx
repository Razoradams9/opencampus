import { RefreshCw } from "lucide-react";
import type { BackendHealth } from "../../lib/useBackendHealth";

function formatUptime(seconds: number): string {
  if (seconds < 60) return `${Math.floor(seconds)} s`;
  if (seconds < 3600) return `${Math.floor(seconds / 60)} min`;
  return `${(seconds / 3600).toFixed(1)} h`;
}

const HEADLINE = {
  checking: { text: "Checking…", tone: "text-pending" },
  online: { text: "Connected", tone: "text-success" },
  offline: { text: "Not connected", tone: "text-danger" },
} as const;

/** Live result of GET /api/health (carried over from M0). */
export function SystemStatus({ health }: { health: BackendHealth }) {
  const { state, data, error, latencyMs, checkedAt, refresh } = health;
  const headline = HEADLINE[state];

  const rows: [string, string][] = [
    ["Endpoint", "GET /api/health"],
    ["Version", data ? `v${data.version}` : "—"],
    ["Environment", data?.environment ?? "—"],
    ["Latency", latencyMs !== null ? `${latencyMs} ms` : "—"],
    ["Uptime", data ? formatUptime(data.uptime_seconds) : "—"],
    ["Last check", checkedAt ? checkedAt.toLocaleTimeString() : "—"],
  ];

  return (
    <section aria-labelledby="status-title" className="oc-panel flex flex-col">
      <header className="flex items-center justify-between border-b border-line px-5 py-3 sm:px-6">
        <h2 id="status-title" className="oc-eyebrow">
          System status
        </h2>
        <button
          type="button"
          onClick={refresh}
          disabled={state === "checking"}
          className="oc-press inline-flex items-center gap-1.5 rounded-oc px-2 py-1 text-xs font-medium text-accent hover:bg-accent-soft disabled:cursor-wait disabled:opacity-60"
        >
          <RefreshCw className={`size-3.5 ${state === "checking" ? "animate-spin" : ""}`} aria-hidden="true" />
          Recheck
        </button>
      </header>
      <div className="px-5 pt-4 sm:px-6">
        <p className={`font-display text-xl font-medium ${headline.tone}`}>{headline.text}</p>
        {state === "offline" && (
          <p className="mt-1 text-xs text-ink-muted">{error ?? "Backend unreachable"}. Is the API running on port 8000?</p>
        )}
      </div>
      <dl className="mt-2 divide-y divide-line px-5 pb-2 text-xs sm:px-6">
        {rows.map(([label, value]) => (
          <div key={label} className="flex justify-between gap-4 py-1.5">
            <dt className="text-ink-subtle">{label}</dt>
            <dd className="truncate font-mono text-ink">{value}</dd>
          </div>
        ))}
      </dl>
    </section>
  );
}
