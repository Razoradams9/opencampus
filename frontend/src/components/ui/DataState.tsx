import { AlertCircle, Loader2 } from "lucide-react";
import type { ReactNode } from "react";

/** Loading / error / empty states shared by real-data panels. */
export function Loading({ label }: { label: string }) {
  return (
    <p role="status" className="flex items-center gap-2 px-5 py-6 text-sm text-ink-subtle sm:px-6">
      <Loader2 className="size-4 animate-spin" aria-hidden="true" /> {label}
    </p>
  );
}

export function LoadError({ error, onRetry }: { error: Error; onRetry: () => void }) {
  return (
    <div role="alert" className="flex flex-wrap items-center gap-3 px-5 py-6 text-sm sm:px-6">
      <AlertCircle className="size-4 text-danger" aria-hidden="true" />
      <span className="text-ink-muted">{error.message}</span>
      <button type="button" onClick={onRetry} className="rounded-oc px-2 py-1 font-medium text-accent hover:bg-sunken">
        Try again
      </button>
    </div>
  );
}

export function Empty({ title, children }: { title: string; children?: ReactNode }) {
  return (
    <div className="px-5 py-8 sm:px-6">
      <p className="font-display text-lg font-medium">{title}</p>
      {children && <p className="mt-1 max-w-prose text-sm text-ink-muted">{children}</p>}
    </div>
  );
}
