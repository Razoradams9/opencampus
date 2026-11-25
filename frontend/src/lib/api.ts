/**
 * Thin client for the OpenCampus REST API.
 * VITE_API_BASE_URL is empty by default, so requests are same-origin and
 * the Vite dev proxy forwards /api to FastAPI.
 */
const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL ?? "").replace(/\/$/, "");

export class ApiError extends Error {
  readonly status?: number;
  readonly code?: string;

  constructor(message: string, status?: number, code?: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
  }
}

export interface RequestOptions {
  method?: "GET" | "POST" | "PATCH" | "DELETE";
  body?: unknown;
  headers?: Record<string, string>;
  signal?: AbortSignal;
}

/** JSON request. Cookies are sent (needed for the refresh endpoint). */
export async function apiRequest<T>(path: string, options: RequestOptions = {}): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      method: options.method ?? "GET",
      credentials: API_BASE_URL ? "include" : "same-origin",
      headers: {
        Accept: "application/json",
        ...(options.body !== undefined ? { "Content-Type": "application/json" } : {}),
        ...options.headers,
      },
      body: options.body !== undefined ? JSON.stringify(options.body) : undefined,
      signal: options.signal,
    });
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") throw error;
    throw new ApiError("Backend unreachable");
  }

  if (!response.ok) {
    // 502–504 come from a proxy (e.g. the Vite dev server) that cannot reach FastAPI.
    if (response.status >= 502 && response.status <= 504) {
      throw new ApiError(`Backend unreachable (HTTP ${response.status})`, response.status);
    }
    let message = `Request failed with HTTP ${response.status}`;
    let code: string | undefined;
    try {
      const body = (await response.json()) as { detail?: unknown; code?: string };
      code = body.code;
      if (typeof body.detail === "string") message = body.detail;
      else if (Array.isArray(body.detail) && body.detail.length > 0) {
        // FastAPI validation errors: report the first one in plain language.
        const first = body.detail[0] as { loc?: unknown[]; msg?: string };
        const field = String(first.loc?.at(-1) ?? "input").replace(/_/g, " ");
        message = `${field[0].toUpperCase()}${field.slice(1)}: ${first.msg ?? "invalid value"}`;
      }
    } catch {
      /* non-JSON error body */
    }
    throw new ApiError(message, response.status, code);
  }
  if (response.status === 204) return undefined as T;
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
  return apiRequest<HealthResponse>("/api/health", { signal });
}
