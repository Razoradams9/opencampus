import { useEffect, useState, type ReactNode } from "react";
import { Sidebar } from "../components/Sidebar";
import { TopBar } from "../components/TopBar";
import type { BackendHealth } from "../lib/useBackendHealth";

interface AppShellProps {
  health: BackendHealth;
  children: ReactNode;
}

/**
 * Persistent frame: fixed sidebar on desktop (≥1024px), slide-in drawer
 * below that, sticky top bar, scrollable main column.
 */
export function AppShell({ health, children }: AppShellProps) {
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
      <Sidebar open={navOpen} onClose={() => setNavOpen(false)} version={health.data?.version ?? null} />

      <div className="lg:pl-(--oc-sidebar-width)">
        <TopBar onMenuClick={() => setNavOpen(true)} menuOpen={navOpen} connection={health.state} />
        <main className="mx-auto max-w-6xl px-4 pt-8 pb-16 sm:px-6 lg:px-10 lg:pt-12">{children}</main>
      </div>
    </div>
  );
}
