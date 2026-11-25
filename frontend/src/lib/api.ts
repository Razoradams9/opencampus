/**
 * Thin client for the OpenCampus REST API.
 * VITE_API_BASE_URL is empty by default, so requests are same-origin and
 * the Vite dev proxy forwards /api to FastAPI.
 */
const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL ?? "").replace(/\/$/, "");

export class ApiError extends Error {
  readonly status?: number;

  constructor(message: string, status?: number) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

async function getJson<T>(path: string, signal?: AbortSignal): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      headers: { Accept: "application/json" },
      signal,
    });
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") throw error;
    throw new ApiError("Backend unreachable");
  }

  if (!response.ok) {
    // 502–504 come from a proxy (e.g. the Vite dev server) that cannot reach FastAPI.
    const message =
      response.status >= 502 && response.status <= 504
        ? `Backend unreachable (HTTP ${response.status})`
        : `Request failed with HTTP ${response.status}`;
    throw new ApiError(message, response.status);
  }
  return (await response.json()) as T;
}

export interface HealthResponse {
  status: string;
  service: string;
  version: string;
  environment: string;
  timestamp: string;
  uptime_seconds: number;
}

export function fetchHealth(signal?: AbortSignal): Promise<HealthResponse> {
  return getJson<HealthResponse>("/api/health", signal);
}
