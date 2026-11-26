import { CalendarClock, House, ListChecks, Menu, Megaphone } from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { useEffect, useState } from "react";

interface Tab {
  id: string;
  label: string;
  icon: LucideIcon;
}

// Each tab jumps to a dashboard section that exists on this page.
const TABS: Tab[] = [
  { id: "home", label: "Home", icon: House },
  { id: "schedule", label: "Classes", icon: CalendarClock },
  { id: "tasks", label: "Tasks", icon: ListChecks },
  { id: "campus", label: "Campus", icon: Megaphone },
];

/** Floating thumb-reach navigation for phones and tablets (hidden at ≥1024px). */
export function MobileTabBar({ onMenu }: { onMenu: () => void }) {
  const [active, setActive] = useState("home");

  // Highlight the section currently crossing the middle of the screen.
  useEffect(() => {
    const observer = new IntersectionObserver(
      (entries) => {
        const visible = entries.find((e) => e.isIntersecting);
        if (visible) setActive(visible.target.id);
      },
      { rootMargin: "-45% 0px -50% 0px" },
    );
    TABS.forEach(({ id }) => {
      const el = document.getElementById(id);
      if (el) observer.observe(el);
    });
    return () => observer.disconnect();
  }, []);

  const go = (id: string) => {
    setActive(id);
    const el = document.getElementById(id);
    if (id === "home" || !el) window.scrollTo({ top: 0, behavior: "smooth" });
    else el.scrollIntoView({ behavior: "smooth", block: "start" });
  };

  const itemClass =
    "relative flex flex-1 flex-col items-center justify-center gap-0.5 text-[0.6875rem] font-medium transition-colors duration-(--oc-dur-micro)";

  return (
    <nav
      aria-label="Sections"
      className="fixed inset-x-3 bottom-[max(0.75rem,env(safe-area-inset-bottom))] z-20 rounded-2xl border border-white/70 bg-surface/90 shadow-e3 backdrop-blur-md lg:hidden"
    >
      <ul className="relative flex h-16">
        {/* One indicator that slides between tabs (transform only). */}
        <li aria-hidden="true" className="pointer-events-none absolute inset-y-0 left-0 w-1/5 transition-transform duration-(--oc-dur-ui) ease-(--oc-ease-standard)" style={{ transform: `translateX(${Math.max(0, TABS.findIndex((t) => t.id === active)) * 100}%)` }}>
          <span className="mx-auto mt-[9px] block h-7 w-12 rounded-full bg-hero/12" />
        </li>
        {TABS.map(({ id, label, icon: Icon }) => {
          const isActive = active === id;
          return (
            <li key={id} className="flex flex-1">
              <button
                type="button"
                onClick={() => go(id)}
                aria-current={isActive ? "location" : undefined}
                className={`oc-press ${itemClass} ${isActive ? "text-hero" : "text-ink-subtle hover:text-ink"}`}
              >
                <span className="relative grid h-7 w-12 place-items-center">
                  <Icon className="size-5" aria-hidden="true" />
                </span>
                {label}
              </button>
            </li>
          );
        })}
        <li className="flex flex-1">
          <button type="button" onClick={onMenu} aria-controls="oc-sidebar" className={`oc-press ${itemClass} text-ink-subtle hover:text-ink`}>
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
