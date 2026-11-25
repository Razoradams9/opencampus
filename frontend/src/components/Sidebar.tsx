import { BookOpen, CalendarDays, Landmark, LayoutDashboard, Users, X } from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { BrandMark } from "./BrandMark";

interface NavItem {
  label: string;
  icon: LucideIcon;
}

// Planned areas are listed so the information architecture is visible,
// but they are disabled: nothing behind them exists yet.
const PLANNED: NavItem[] = [
  { label: "Courses", icon: BookOpen },
  { label: "Timetable", icon: CalendarDays },
  { label: "People", icon: Users },
  { label: "Administration", icon: Landmark },
];

interface SidebarProps {
  open: boolean;
  onClose: () => void;
  version: string | null;
}

export function Sidebar({ open, onClose, version }: SidebarProps) {
  return (
    <>
      {/* Scrim for the mobile/tablet drawer */}
      <div
        className={`fixed inset-0 z-30 bg-ink/30 transition-opacity lg:hidden ${
          open ? "opacity-100" : "pointer-events-none opacity-0"
        }`}
        onClick={onClose}
        aria-hidden="true"
      />

      <aside
        id="oc-sidebar"
        className={`fixed inset-y-0 left-0 z-40 flex w-(--oc-sidebar-width) flex-col border-r border-line bg-surface transition-[translate,visibility] duration-200 lg:visible lg:translate-x-0 ${
          open ? "visible translate-x-0" : "invisible -translate-x-full"
        }`}
        aria-label="Primary"
      >
        <div className="flex h-(--oc-topbar-height) items-center justify-between px-5">
          <BrandMark />
          <button
            type="button"
            onClick={onClose}
            className="rounded-oc p-1.5 text-ink-muted hover:bg-sunken lg:hidden"
            aria-label="Close navigation"
          >
            <X className="size-5" />
          </button>
        </div>

        <nav className="flex-1 overflow-y-auto px-3 pt-4">
          <a
            href="/"
            aria-current="page"
            className="relative flex items-center gap-3 rounded-oc bg-accent-soft px-3 py-2 text-sm font-medium text-accent"
          >
            <span className="absolute inset-y-1.5 left-0 w-0.5 rounded-full bg-accent" aria-hidden="true" />
            <LayoutDashboard className="size-4" />
            Dashboard
          </a>

          <p className="oc-eyebrow mt-8 mb-2 px-3">Planned</p>
          <ul className="space-y-0.5">
            {PLANNED.map(({ label, icon: Icon }) => (
              <li key={label}>
                <span
                  aria-disabled="true"
                  title="Not available yet"
                  className="flex cursor-not-allowed items-center gap-3 px-3 py-2 text-sm text-ink-subtle"
                >
                  <Icon className="size-4" />
                  {label}
                </span>
              </li>
            ))}
          </ul>
        </nav>

        <div className="border-t border-line px-5 py-4">
          <p className="oc-eyebrow">Foundation · M0</p>
          <p className="mt-1 font-mono text-xs text-ink-muted">
            API {version ? `v${version}` : "version unknown"}
          </p>
        </div>
      </aside>
    </>
  );
}
