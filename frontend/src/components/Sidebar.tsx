import {
  BookOpen,
  CalendarRange,
  ClipboardList,
  FolderOpen,
  Home,
  LogOut,
  NotebookPen,
  Sparkles,
  Trees,
  X,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { useState } from "react";
import { ROLE_LABEL, type Me } from "../lib/auth/types";
import { Link } from "../lib/router";
import { BrandMark } from "./BrandMark";
import { InstitutionSwitcher } from "./InstitutionSwitcher";
import { SoonTag } from "./ui/SoonTag";

interface NavItem {
  label: string;
  icon: LucideIcon;
}

// Modules are listed so the product's shape is visible; none exist yet.
const UPCOMING: NavItem[] = [
  { label: "Academics", icon: BookOpen },
  { label: "Assignments", icon: ClipboardList },
  { label: "Resources", icon: FolderOpen },
  { label: "AI Assistant", icon: Sparkles },
  { label: "Campus Life", icon: Trees },
  { label: "Notes", icon: NotebookPen },
  { label: "Planner", icon: CalendarRange },
];

interface SidebarProps {
  open: boolean;
  onClose: () => void;
  me: Me;
  onSwitchInstitution: (institutionId: string) => Promise<void>;
  onLogout: () => Promise<void>;
}

function initials(name: string): string {
  const parts = name.split(/\s+/).filter(Boolean);
  return ((parts[0]?.[0] ?? "") + (parts.length > 1 ? parts[parts.length - 1][0] : "")).toUpperCase();
}

export function Sidebar({ open, onClose, me, onSwitchInstitution, onLogout }: SidebarProps) {
  const [signingOut, setSigningOut] = useState(false);
  const role = me.active_institution ? ROLE_LABEL[me.active_institution.role] : null;
  const roleLine = [me.user.is_platform_admin ? "Platform admin" : null, role].filter(Boolean).join(" · ") || "No role";

  return (
    <>
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
          <Link
            to="/"
            aria-current="page"
            onClick={onClose}
            className="relative flex items-center gap-3 rounded-oc bg-accent-soft px-3 py-2 text-sm font-medium text-accent"
          >
            <span className="absolute inset-y-1.5 left-0 w-0.5 rounded-full bg-accent" aria-hidden="true" />
            <Home className="size-4" aria-hidden="true" />
            Home
          </Link>

          <p className="oc-eyebrow mt-6 mb-1.5 px-3">Coming soon</p>
          <ul>
            {UPCOMING.map(({ label, icon: Icon }) => (
              <li key={label}>
                <span
                  aria-disabled="true"
                  className="flex cursor-not-allowed items-center gap-3 px-3 py-[0.4375rem] text-sm text-ink-subtle"
                >
                  <Icon className="size-4" aria-hidden="true" />
                  <span className="flex-1">{label}</span>
                  <SoonTag />
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
