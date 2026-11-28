import { BookOpen, CalendarClock, House, ListChecks, Menu } from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { navigate } from "../lib/router";

interface Tab {
  id: string;
  label: string;
  icon: LucideIcon;
  /** Page the tab opens. */
  to: string;
  /** Dashboard section to scroll to after opening "/". */
  section?: string;
}

const TABS: Tab[] = [
  { id: "home", label: "Home", icon: House, to: "/" },
  { id: "timetable", label: "Classes", icon: CalendarClock, to: "/timetable" },
  { id: "academics", label: "Courses", icon: BookOpen, to: "/academics" },
  { id: "tasks", label: "Tasks", icon: ListChecks, to: "/assignments" },
];

function scrollToSection(id: string, attempts = 10) {
  const el = document.getElementById(id);
  if (el) el.scrollIntoView({ behavior: "smooth", block: "start" });
  else if (attempts > 0) requestAnimationFrame(() => scrollToSection(id, attempts - 1));
}

/** Floating thumb-reach navigation for phones and tablets (hidden at ≥1024px). */
export function MobileTabBar({ pathname, onMenu }: { pathname: string; onMenu: () => void }) {
  const active = TABS.find((t) => t.to === pathname && !t.section)?.id;

  const go = (tab: Tab) => {
    if (tab.section) {
      navigate(tab.to);
      scrollToSection(tab.section);
    } else if (pathname === tab.to) {
      window.scrollTo({ top: 0, behavior: "smooth" });
    } else {
      navigate(tab.to);
      window.scrollTo({ top: 0 });
    }
  };

  const itemClass = "flex flex-1 flex-col items-center justify-center gap-0.5 text-[0.6875rem] font-medium transition-colors";

  return (
    <nav
      aria-label="Sections"
      className="fixed inset-x-3 bottom-[max(0.75rem,env(safe-area-inset-bottom))] z-20 rounded-2xl border border-white/70 bg-surface/90 shadow-e3 backdrop-blur-md lg:hidden"
    >
      <ul className="flex h-16">
        {TABS.map((tab) => {
          const isActive = active === tab.id;
          const Icon = tab.icon;
          return (
            <li key={tab.id} className="flex flex-1">
              <button
                type="button"
                onClick={() => go(tab)}
                aria-current={isActive ? (tab.section ? "location" : "page") : undefined}
                className={`${itemClass} ${isActive ? "text-accent" : "text-ink-subtle hover:text-ink"}`}
              >
                <span className={`grid h-7 w-12 place-items-center rounded-full transition-colors duration-150 ${isActive ? "bg-accent-soft" : ""}`}>
                  <Icon className="size-5" aria-hidden="true" />
                </span>
                {tab.label}
              </button>
            </li>
          );
        })}
        <li className="flex flex-1">
          <button type="button" onClick={onMenu} aria-controls="oc-sidebar" className={`${itemClass} text-ink-subtle hover:text-ink`}>
            <span className="grid h-7 w-12 place-items-center">
              <Menu className="size-5" aria-hidden="true" />
            </span>
            Menu
          </button>
        </li>
      </ul>
    </nav>
  );
}
