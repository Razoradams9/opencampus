import { useCallback, useEffect, useRef, useState } from "react";
import { ApiError, fetchHealth, type HealthResponse } from "./api";

export type ConnectionState = "checking" | "online" | "offline";

export interface BackendHealth {
  state: ConnectionState;
  data: HealthResponse | null;
  error: string | null;
  latencyMs: number | null;
  checkedAt: Date | null;
  refresh: () => void;
}

const POLL_INTERVAL_MS = 30_000;
const TIMEOUT_MS = 5_000;

/** Polls GET /api/health and reports the real connection state. */
export function useBackendHealth(): BackendHealth {
  const [state, setState] = useState<ConnectionState>("checking");
  const [data, setData] = useState<HealthResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [latencyMs, setLatencyMs] = useState<number | null>(null);
  const [checkedAt, setCheckedAt] = useState<Date | null>(null);
  const inFlight = useRef<AbortController | null>(null);

  const check = useCallback(async () => {
    inFlight.current?.abort();
    const controller = new AbortController();
    inFlight.current = controller;
    const timeout = window.setTimeout(() => controller.abort("timeout"), TIMEOUT_MS);

    setState("checking");
    const started = performance.now();
    try {
      const result = await fetchHealth(controller.signal);
      setData(result);
      setError(result.status === "ok" ? null : `Backend reported "${result.status}"`);
      setState(result.status === "ok" ? "online" : "offline");
      setLatencyMs(Math.round(performance.now() - started));
    } catch (err) {
      // A superseded request was aborted on purpose; let the newer one report.
      if (inFlight.current !== controller) return;
      setData(null);
      setLatencyMs(null);
      setState("offline");
      if (controller.signal.reason === "timeout") setError("Timed out after 5 s");
      else setError(err instanceof ApiError ? err.message : "Unexpected error");
    } finally {
      window.clearTimeout(timeout);
      if (inFlight.current === controller) setCheckedAt(new Date());
    }
  }, []);

  useEffect(() => {
    void check();
    const id = window.setInterval(() => void check(), POLL_INTERVAL_MS);
    return () => {
      window.clearInterval(id);
      inFlight.current?.abort();
    };
  }, [check]);

  return { state, data, error, latencyMs, checkedAt, refresh: () => void check() };
}
