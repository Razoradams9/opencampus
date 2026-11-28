import { useEffect, useMemo, useState, type ComponentType } from "react";
import { LoadingScreen, NoInstitution, NotFound } from "./components/StatusScreens";
import { createDemoDashboard } from "./data/demo";
import { AppShell } from "./layouts/AppShell";
import { AuthProvider, useAuth } from "./lib/auth/AuthContext";
import type { Me } from "./lib/auth/types";
import { navigate, useLocation } from "./lib/router";
import { useBackendHealth } from "./lib/useBackendHealth";
import { AcademicsPage } from "./pages/AcademicsPage";
import { Dashboard } from "./pages/Dashboard";
import { LearningPage } from "./pages/LearningPage";
import { LoginPage } from "./pages/LoginPage";
import { ForgotPasswordPage } from "./pages/ForgotPasswordPage";
import { RegisterPage } from "./pages/RegisterPage";
import { ResetPasswordPage } from "./pages/ResetPasswordPage";
import { TimetablePage } from "./pages/TimetablePage";

const PUBLIC_ROUTES = new Set(["/login", "/register"]);
/** Signed-in pages inside the app shell. */
const APP_ROUTES = new Set(["/", "/academics", "/timetable", "/learning"]);
// Reachable whether or not someone is signed in (e.g. a reset link opened in
// a browser that still has another session).
const OPEN_ROUTES: Record<string, ComponentType> = {
  "/forgot-password": ForgotPasswordPage,
  "/reset-password": ResetPasswordPage,
};

function Redirect({ to }: { to: string }) {
  useEffect(() => navigate(to, { replace: true }), [to]);
  return null;
}

function AuthenticatedApp({ me, pathname }: { me: Me; pathname: string }) {
  const health = useBackendHealth();
  const today = useMemo(() => new Date(), []);
  const data = useMemo(() => createDemoDashboard(today), [today]);
  const [query, setQuery] = useState("");

  const institution = me.active_institution;
  let page;
  if (!APP_ROUTES.has(pathname)) page = <NotFound />;
  else if (!institution) page = <NoInstitution me={me} />;
  // key: remount on tenant switch so local state never crosses institutions.
  else if (pathname === "/academics") page = <AcademicsPage key={institution.id} institution={institution} />;
  else if (pathname === "/learning") page = <LearningPage key={institution.id} institution={institution} />;
  else if (pathname === "/timetable") page = <TimetablePage key={institution.id} institution={institution} />;
  else
    page = (
      <Dashboard
        key={institution.id}
        user={me.user}
        institution={institution}
        data={data}
        today={today}
        health={health}
        query={query}
        onClearQuery={() => setQuery("")}
      />
    );

  return (
    <AppShell me={me} pathname={pathname} health={health} data={data} today={today} query={query} onQueryChange={setQuery}>
      {page}
    </AppShell>
  );
}

/**
 * Route guard. This is a UX convenience only: every protected API call is
 * authorised by the backend regardless of what the client renders.
 */
function Routes() {
  const { status, me } = useAuth();
  const { pathname, search } = useLocation();

  const OpenPage = OPEN_ROUTES[pathname];
  if (OpenPage) return <OpenPage />;

  if (status === "loading") return <LoadingScreen />;

  if (PUBLIC_ROUTES.has(pathname)) {
    if (status === "authenticated") return <Redirect to="/" />;
    return pathname === "/login" ? <LoginPage /> : <RegisterPage />;
  }

  if (status !== "authenticated" || !me) {
    const next = pathname === "/" ? "" : `?next=${encodeURIComponent(pathname + search)}`;
    return <Redirect to={`/login${next}`} />;
  }
  return <AuthenticatedApp me={me} pathname={pathname} />;
}

export default function App() {
  return (
    <AuthProvider>
      <Routes />
    </AuthProvider>
  );
}
