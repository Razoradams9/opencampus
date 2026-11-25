import type { ConnectionState } from "../lib/useBackendHealth";

const LABELS: Record<ConnectionState, string> = {
  checking: "Checking",
  online: "API online",
  offline: "API offline",
};

const STYLES: Record<ConnectionState, { pill: string; dot: string }> = {
  checking: { pill: "bg-pending-soft text-pending", dot: "bg-pending" },
  online: { pill: "bg-success-soft text-success", dot: "bg-success" },
  offline: { pill: "bg-danger-soft text-danger", dot: "bg-danger" },
};

/** Compact pill that mirrors the live backend connection state. */
export function ConnectionPill({ state }: { state: ConnectionState }) {
  const style = STYLES[state];
  return (
    <span
      role="status"
      aria-live="polite"
      className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium ${style.pill}`}
    >
      <span className={`size-1.5 rounded-full ${style.dot}`} aria-hidden="true" />
      {LABELS[state]}
    </span>
  );
}
