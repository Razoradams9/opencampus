import {
  BookOpen,
  CalendarRange,
  ClipboardList,
  Home,
  Library,
  Megaphone,
  LogOut,
  X,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { useState } from "react";
import { ROLE_LABEL, type Me } from "../lib/auth/types";
import { Link } from "../lib/router";
import { BrandMark } from "./BrandMark";
import { InstitutionSwitcher } from "./InstitutionSwitcher";

interface NavItem {
  label: string;
  icon: LucideIcon;
}

interface PageItem extends NavItem {
  to: string;
}

const PAGES: PageItem[] = [
  { label: "Home", icon: Home, to: "/" },
  { label: "Academics", icon: BookOpen, to: "/academics" },
  { label: "Timetable", icon: CalendarRange, to: "/timetable" },
  { label: "Learning", icon: Library, to: "/learning" },
  { label: "Assignments", icon: ClipboardList, to: "/assignments" },
  { label: "Announcements", icon: Megaphone, to: "/announcements" },
];

// Shown as a brief preview of what is coming.
const UPCOMING: NavItem[] = [];

interface SidebarProps {
  open: boolean;
  onClose: () => void;
  me: Me;
  pathname: string;
  onSwitchInstitution: (institutionId: string) => Promise<void>;
  onLogout: () => Promise<void>;
}

function initials(name: string): string {
  const parts = name.split(/\s+/).filter(Boolean);
  return ((parts[0]?.[0] ?? "") + (parts.length > 1 ? parts[parts.length - 1][0] : "")).toUpperCase();
}

export function Sidebar({ open, onClose, me, pathname, onSwitchInstitution, onLogout }: SidebarProps) {
  const [signingOut, setSigningOut] = useState(false);
  const role = me.active_institution ? ROLE_LABEL[me.active_institution.role] : null;
  const roleLine = [me.user.is_platform_admin ? "Platform admin" : null, role].filter(Boolean).join(" · ") || "No role";

  return (
    <>
      <div
        className={`fixed inset-0 z-30 bg-accent/15 backdrop-blur-[2px] transition-opacity lg:hidden ${
          open ? "opacity-100" : "pointer-events-none opacity-0"
        }`}
        onClick={onClose}
        aria-hidden="true"
      />

      <aside
        id="oc-sidebar"
        className={`fixed inset-y-0 left-0 z-40 flex w-(--oc-sidebar-width) flex-col border-r border-line-strong/60 bg-sidebar transition-[translate,visibility] duration-200 lg:visible lg:translate-x-0 ${
          open ? "visible translate-x-0" : "invisible -translate-x-full"
        }`}
        aria-label="Sidebar"
      >
        <div className="flex h-(--oc-topbar-height) shrink-0 items-center justify-between px-5">
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

        <div className="px-3 pt-1">
          <InstitutionSwitcher me={me} onSwitch={onSwitchInstitution} />
        </div>

        <nav aria-label="Primary" className="flex-1 overflow-y-auto px-3 pt-5 pb-4">
          <ul className="space-y-1">
            {PAGES.map(({ label, icon: Icon, to }) => {
              const current = pathname === to;
              return (
                <li key={to}>
                  <Link
                    to={to}
                    aria-current={current ? "page" : undefined}
                    onClick={onClose}
                    className={`flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-medium transition-colors duration-150 ${
                      current ? "bg-surface text-accent shadow-e1 ring-1 ring-accent/15" : "text-ink-muted hover:bg-surface/70 hover:text-ink"
                    }`}
                  >
                    <Icon className={`size-4 ${current ? "text-accent" : ""}`} aria-hidden="true" />
                    {label}
                  </Link>
                </li>
              );
            })}
          </ul>

          {UPCOMING.length > 0 && <p className="oc-eyebrow mt-6 mb-1.5 px-3">Coming soon</p>}
          <ul>
            {UPCOMING.map(({ label, icon: Icon }) => (
              <li key={label}>
                <span
                  aria-disabled="true"
                  className="flex cursor-not-allowed items-center gap-3 px-3 py-[0.4375rem] text-sm text-ink-subtle/80"
                >
                  <Icon className="size-4" aria-hidden="true" />
                  <span className="flex-1">{label}</span>
                  <span className="sr-only">(not available yet)</span>
                </span>
              </li>
            ))}
          </ul>
        </nav>

        {/* Profile */}
        <div className="flex shrink-0 items-center gap-3 border-t border-line px-4 py-3">
          <span
            className="grid size-9 shrink-0 place-items-center bg-periwinkle font-display text-sm font-medium text-ink"
            aria-hidden="true"
          >
            {initials(me.user.full_name)}
          </span>
          <div className="min-w-0 flex-1">
            <p className="truncate text-sm font-medium">{me.user.full_name}</p>
            <p className="truncate text-[0.6875rem] text-ink-subtle" title={me.user.email}>
              {roleLine}
            </p>
          </div>
          <button
            type="button"
            onClick={async () => {
              setSigningOut(true);
              await onLogout();
            }}
            disabled={signingOut}
            title="Sign out"
            aria-label="Sign out"
            className="grid size-8 place-items-center rounded-oc text-ink-muted transition-colors hover:bg-sunken hover:text-ink disabled:opacity-60"
          >
            <LogOut className="size-4" aria-hidden="true" />
          </button>
        </div>
      </aside>
    </>
  );
}
