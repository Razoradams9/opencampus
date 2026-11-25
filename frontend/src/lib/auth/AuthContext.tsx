import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { apiRequest } from "../api";
import { authRequest, logoutRequest, refreshSession, setAccessToken } from "./session";
import type { Me, RegisterInput, TokenResponse } from "./types";

type AuthStatus = "loading" | "authenticated" | "anonymous";

interface AuthContextValue {
  status: AuthStatus;
  me: Me | null;
  login: (email: string, password: string) => Promise<void>;
  register: (input: RegisterInput) => Promise<void>;
  logout: () => Promise<void>;
  switchInstitution: (institutionId: string) => Promise<void>;
  /** Drop local auth state after the server revoked the session (e.g. password reset). */
  forgetSession: () => void;
}

const AuthContext = createContext<AuthContextValue | null>(null);

/** Refresh this long before the access token expires. */
const REFRESH_LEAD_SECONDS = 60;

export function AuthProvider({ children }: { children: ReactNode }) {
  const [status, setStatus] = useState<AuthStatus>("loading");
  const [me, setMe] = useState<Me | null>(null);
  const timer = useRef<number | undefined>(undefined);

  const signOutLocally = useCallback(() => {
    window.clearTimeout(timer.current);
    setAccessToken(null);
    setMe(null);
    setStatus("anonymous");
  }, []);

  const accept = useCallback(
    (tokens: TokenResponse) => {
      setAccessToken(tokens.access_token);
      setMe(tokens.me);
      setStatus("authenticated");
      // Keep the in-memory access token fresh while the tab is open.
      window.clearTimeout(timer.current);
      const delay = Math.max(tokens.expires_in - REFRESH_LEAD_SECONDS, 15) * 1000;
      timer.current = window.setTimeout(() => {
        refreshSession().then(accept, signOutLocally);
      }, delay);
    },
    [signOutLocally],
  );

  // On load, the HttpOnly refresh cookie (if any) restores the session.
  useEffect(() => {
    refreshSession().then(accept, signOutLocally);
    return () => window.clearTimeout(timer.current);
  }, [accept, signOutLocally]);

  const value = useMemo<AuthContextValue>(
    () => ({
      status,
      me,
      login: async (email, password) => {
        accept(await apiRequest<TokenResponse>("/api/auth/login", { method: "POST", body: { email, password } }));
      },
      register: async (input) => {
        accept(await apiRequest<TokenResponse>("/api/auth/register", { method: "POST", body: input }));
      },
      logout: async () => {
        try {
          await logoutRequest();
        } finally {
          signOutLocally();
        }
      },
      forgetSession: signOutLocally,
      switchInstitution: async (institutionId) => {
        try {
          setMe(await authRequest<Me>("/api/auth/switch-institution", { method: "POST", body: { institution_id: institutionId } }));
        } catch (error) {
          if (error instanceof Error && "status" in error && error.status === 401) signOutLocally();
          throw error;
        }
      },
    }),
    [status, me, accept, signOutLocally],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext);
  if (!context) throw new Error("useAuth must be used inside <AuthProvider>");
  return context;
}
