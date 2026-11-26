import { Bell } from "lucide-react";
import { useEffect, useId, useRef, useState } from "react";
import type { CampusUpdate } from "../data/types";
import { formatRelativeDay } from "../lib/dates";

interface NotificationsMenuProps {
  /** Important campus updates from the demo data. */
  items: CampusUpdate[];
  today: Date;
}

/**
 * Disclosure panel listing important campus updates. There is no
 * notification service yet; the panel says so instead of implying one.
 */
export function NotificationsMenu({ items, today }: NotificationsMenuProps) {
  const [open, setOpen] = useState(false);
  const panelId = useId();
  const rootRef = useRef<HTMLDivElement>(null);
  const buttonRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (!open) return;
    const onPointer = (event: PointerEvent) => {
      if (!rootRef.current?.contains(event.target as Node)) setOpen(false);
    };
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        setOpen(false);
        buttonRef.current?.focus();
      }
    };
    document.addEventListener("pointerdown", onPointer);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("pointerdown", onPointer);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  return (
    <div ref={rootRef} className="relative">
      <button
        ref={buttonRef}
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        aria-controls={panelId}
        aria-label={`Notifications, ${items.length} important`}
        title="Notifications"
        className={`relative grid size-9 place-items-center rounded-oc text-ink-muted transition-colors hover:bg-sunken hover:text-ink ${
          open ? "bg-sunken text-ink" : ""
        }`}
      >
        <Bell className="size-[1.125rem]" aria-hidden="true" />
        {/* A calm dot, not a counter: the panel shows what's there. */}
        {items.length > 0 && <span className="absolute top-2 right-2 size-2 rounded-full bg-accent ring-2 ring-canvas" aria-hidden="true" />}
      </button>

      {open && (
        <div
          id={panelId}
          role="region"
          aria-label="Notifications"
          className="absolute right-0 z-30 mt-2 w-[min(20rem,calc(100vw-2rem))] overflow-hidden rounded-card bg-surface shadow-e3"
        >
          <div className="flex items-center justify-between border-b border-line px-4 py-2.5">
            <p className="oc-eyebrow">Important updates</p>
            <span className="text-[0.6875rem] text-ink-subtle">Demo data</span>
          </div>
          {items.length === 0 ? (
            <p className="px-4 py-4 text-sm text-ink-subtle">Nothing important right now.</p>
          ) : (
            <ul className="divide-y divide-line">
              {items.map((u) => (
                <li key={u.id} className="px-4 py-3">
                  <p className="text-sm font-medium">{u.title}</p>
                  <p className="mt-0.5 font-mono text-[0.6875rem] text-ink-subtle">
                    {u.category} · {formatRelativeDay(u.date, today)}
                  </p>
                </li>
              ))}
            </ul>
          )}
          <p className="border-t border-line bg-canvas/60 px-4 py-2.5 text-[0.6875rem] text-ink-subtle">
            Live notifications are not available yet.
          </p>
        </div>
      )}
    </div>
  );
}
