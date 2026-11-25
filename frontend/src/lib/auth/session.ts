/**
 * Token handling, outside React.
 *
 * - The access token lives only in this module's memory: never in
 *   localStorage/sessionStorage, so an XSS payload cannot read it from storage
 *   and it disappears when the tab closes.
 * - The refresh token is an HttpOnly cookie the browser sends to /api/auth
 *   only; JavaScript never sees it.
 * - Refresh calls are de-duplicated: rotation makes a refresh token single-
 *   use, so two parallel refreshes would otherwise race.
 */
import { ApiError, apiRequest, type RequestOptions } from "../api";
import type { TokenResponse } from "./types";

let accessToken: string | null = null;
let inflightRefresh: Promise<TokenResponse> | null = null;

export function setAccessToken(token: string | null) {
  accessToken = token;
}

function readCookie(name: string): string | null {
  const match = document.cookie.split("; ").find((part) => part.startsWith(`${name}=`));
  return match ? decodeURIComponent(match.slice(name.length + 1)) : null;
}

/** CSRF double-submit value (cookie name depends on Secure mode). */
function csrfHeader(): Record<string, string> {
  const token = readCookie("__Secure-oc_csrf") ?? readCookie("oc_csrf");
  return token ? { "X-CSRF-Token": token } : {};
}

const wait = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));

async function doRefresh(): Promise<TokenResponse> {
  try {
    return await apiRequest<TokenResponse>("/api/auth/refresh", { method: "POST", headers: csrfHeader() });
  } catch (error) {
    // Another tab rotated the token a moment ago; the browser now holds the
    // new cookie, so a single retry succeeds.
    if (error instanceof ApiError && error.code === "refresh_superseded") {
      await wait(250);
      return apiRequest<TokenResponse>("/api/auth/refresh", { method: "POST", headers: csrfHeader() });
    }
    throw error;
  }
}

export function refreshSession(): Promise<TokenResponse> {
  inflightRefresh ??= doRefresh()
    .then((result) => {
      accessToken = result.access_token;
      return result;
    })
    .finally(() => {
      inflightRefresh = null;
    });
  return inflightRefresh;
}

export async function logoutRequest(): Promise<void> {
  try {
    await apiRequest<void>("/api/auth/logout", { method: "POST", headers: csrfHeader() });
  } finally {
    accessToken = null;
  }
}

/**
 * Authenticated request. On 401 it refreshes once and retries; if that fails
 * the error propagates and the caller treats the user as signed out.
 */
export async function authRequest<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const send = () =>
    apiRequest<T>(path, {
      ...options,
      headers: { ...options.headers, ...(accessToken ? { Authorization: `Bearer ${accessToken}` } : {}) },
    });
  try {
    return await send();
  } catch (error) {
    if (!(error instanceof ApiError) || error.status !== 401) throw error;
    await refreshSession();
    return send();
  }
}
