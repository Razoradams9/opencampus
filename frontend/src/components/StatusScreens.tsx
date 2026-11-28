import { Building2, Loader2 } from "lucide-react";
import type { Me } from "../lib/auth/types";
import { BrandMark } from "./BrandMark";

export function LoadingScreen() {
  return (
    <div className="grid min-h-dvh place-items-center" role="status" aria-live="polite">
      <div className="flex flex-col items-center gap-4">
        <BrandMark />
        <p className="flex items-center gap-2 text-sm text-ink-subtle">
          <Loader2 className="size-4 animate-spin" aria-hidden="true" /> Restoring your session…
        </p>
      </div>
    </div>
  );
}

/** Signed in, but no active membership: nothing tenant-scoped can be shown. */
export function NoInstitution({ me }: { me: Me }) {
  return (
    <section className="oc-panel mx-auto mt-6 max-w-xl px-6 py-8 sm:px-8" aria-labelledby="no-institution-title">
      <Building2 className="size-6 text-ink-subtle" aria-hidden="true" />
      <h1 id="no-institution-title" className="mt-4 font-display text-2xl font-medium tracking-tight">
        No active institution
      </h1>
      <p className="mt-2 text-sm leading-relaxed text-ink-muted">
        {me.user.is_platform_admin
          ? "Your account is a platform administrator without a college membership. Institutions are managed through the platform API for now."
          : "Your account is not currently linked to an active college. If you expected access, contact your college's administrator."}
      </p>
      {me.memberships.length > 0 && (
        <ul className="mt-5 divide-y divide-line border-y border-line text-sm">
          {me.memberships.map((m) => (
            <li key={m.id} className="flex justify-between gap-4 py-2">
              <span>{m.institution.name}</span>
              <span className="font-mono text-xs text-ink-subtle">
                {m.status !== "active" ? `membership ${m.status}` : `institution ${m.institution.status}`}
              </span>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

export function NotFound() {
  return (
    <section className="oc-panel mx-auto mt-6 max-w-xl px-6 py-8 sm:px-8">
      <p className="oc-eyebrow">404</p>
      <h1 className="mt-2 font-display text-2xl font-medium">This page does not exist yet.</h1>
      <p className="mt-2 text-sm text-ink-muted">Use the navigation to reach Home, Academics, Timetable and the other pages.</p>
    </section>
  );
}
