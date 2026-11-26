import { Building2, Check, ChevronsUpDown } from "lucide-react";
import { useEffect, useId, useRef, useState } from "react";
import type { Me } from "../lib/auth/types";
import { ROLE_LABEL } from "../lib/auth/types";

interface InstitutionSwitcherProps {
  me: Me;
  onSwitch: (institutionId: string) => Promise<void>;
}

/**
 * Shows the session's active institution. With more than one usable
 * membership it becomes a menu; the server re-checks membership on switch.
 */
export function InstitutionSwitcher({ me, onSwitch }: InstitutionSwitcherProps) {
  const [open, setOpen] = useState(false);
  const [pending, setPending] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const menuId = useId();
  const rootRef = useRef<HTMLDivElement>(null);
  const active = me.active_institution;
  const options = me.memberships.filter((m) => m.status === "active" && m.institution.status === "active");

  useEffect(() => {
    if (!open) return;
    const onPointer = (e: PointerEvent) => {
      if (!rootRef.current?.contains(e.target as Node)) setOpen(false);
    };
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && setOpen(false);
    document.addEventListener("pointerdown", onPointer);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("pointerdown", onPointer);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  const summary = (
    <>
      <Building2 className="size-4 shrink-0 text-ink-subtle" aria-hidden="true" />
      <span className="min-w-0 flex-1">
        <span className="block truncate text-sm font-medium text-ink">{active?.name ?? "No institution"}</span>
        <span className="block truncate text-[0.6875rem] text-ink-subtle">
          {active ? `${ROLE_LABEL[active.role]} · ${active.slug}` : "No active membership"}
        </span>
      </span>
    </>
  );

  if (options.length <= 1) {
    return <div className="flex w-full items-center gap-3 rounded-xl bg-surface/80 px-3 py-2 shadow-e1">{summary}</div>;
  }

  const choose = async (institutionId: string) => {
    if (institutionId === active?.id) return setOpen(false);
    setPending(institutionId);
    setError(null);
    try {
      await onSwitch(institutionId);
      setOpen(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not switch institution");
    } finally {
      setPending(null);
    }
  };

  return (
    <div ref={rootRef} className="relative">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        aria-controls={menuId}
        aria-label={`Institution: ${active?.name ?? "none"}. Switch institution`}
        className="flex w-full items-center gap-3 rounded-xl bg-surface/80 px-3 py-2 text-left shadow-e1 transition-shadow hover:shadow-e2"
      >
        {summary}
        <ChevronsUpDown className="size-3.5 shrink-0 text-ink-subtle" aria-hidden="true" />
      </button>
      {open && (
        <div id={menuId} className="oc-pop-in absolute inset-x-0 z-10 mt-1.5 overflow-hidden rounded-card bg-surface shadow-e3 [--oc-origin:top_center]">
          <p className="oc-eyebrow border-b border-line px-3 py-2">Switch institution</p>
          <ul>
            {options.map((m) => (
              <li key={m.id}>
                <button
                  type="button"
                  onClick={() => choose(m.institution.id)}
                  disabled={pending !== null}
                  aria-current={m.institution.id === active?.id ? "true" : undefined}
                  className="flex w-full items-center gap-2 px-3 py-2 text-left hover:bg-sunken disabled:opacity-60"
                >
                  <span className="min-w-0 flex-1">
                    <span className="block truncate text-sm">{m.institution.name}</span>
                    <span className="block text-[0.6875rem] text-ink-subtle">{ROLE_LABEL[m.role]}</span>
                  </span>
                  {m.institution.id === active?.id && <Check className="size-4 text-accent" aria-hidden="true" />}
                  {pending === m.institution.id && <span className="text-[0.6875rem] text-ink-subtle">Switching…</span>}
                </button>
              </li>
            ))}
          </ul>
          {error && (
            <p role="alert" className="border-t border-line px-3 py-2 text-xs text-danger">
              {error}
            </p>
          )}
        </div>
      )}
    </div>
  );
}
