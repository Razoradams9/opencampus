import { useEffect, useState, type ReactNode } from "react";
import { Sidebar } from "../components/Sidebar";
import { TopBar } from "../components/TopBar";
import type { DashboardData } from "../data/types";
import { useAuth } from "../lib/auth/AuthContext";
import type { Me } from "../lib/auth/types";
import type { BackendHealth } from "../lib/useBackendHealth";

interface AppShellProps {
  me: Me;
  health: BackendHealth;
  data: DashboardData;
  today: Date;
  query: string;
  onQueryChange: (value: string) => void;
  children: ReactNode;
}

/**
 * Persistent frame: fixed sidebar on desktop (≥1024px), slide-in drawer
 * below that, sticky top bar, scrollable main column.
 */
export function AppShell({ me, health, data, today, query, onQueryChange, children }: AppShellProps) {
  const { logout, switchInstitution } = useAuth();
  const [navOpen, setNavOpen] = useState(false);

  useEffect(() => {
    if (!navOpen) return;
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") setNavOpen(false);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [navOpen]);

  return (
    <div className="min-h-dvh">
      <a
        href="#main"
        className="sr-only focus:not-sr-only focus:fixed focus:top-2 focus:left-2 focus:z-50 focus:bg-ink focus:px-3 focus:py-2 focus:text-sm focus:text-canvas"
      >
        Skip to content
      </a>

      <Sidebar
        open={navOpen}
        onClose={() => setNavOpen(false)}
        me={me}
        onSwitchInstitution={switchInstitution}
        onLogout={logout}
      />

      <div className="lg:pl-(--oc-sidebar-width)">
        <TopBar
          onMenuClick={() => setNavOpen(true)}
          menuOpen={navOpen}
          connection={health.state}
          query={query}
          onQueryChange={onQueryChange}
          notifications={data.updates.filter((u) => u.important)}
          today={today}
        />
        <main id="main" className="mx-auto max-w-[78rem] px-4 pt-6 pb-16 sm:px-6 lg:px-10 lg:pt-8">
          {children}
        </main>
      </div>
    </div>
  );
}
