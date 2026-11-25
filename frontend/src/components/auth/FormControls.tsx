import { AlertCircle, Loader2 } from "lucide-react";
import type { InputHTMLAttributes, ReactNode } from "react";

interface FieldProps extends InputHTMLAttributes<HTMLInputElement> {
  id: string;
  label: string;
  hint?: ReactNode;
}

export function Field({ id, label, hint, ...input }: FieldProps) {
  const hintId = hint ? `${id}-hint` : undefined;
  return (
    <div>
      <label htmlFor={id} className="block text-sm font-medium text-ink">
        {label}
      </label>
      <input
        id={id}
        aria-describedby={hintId}
        className="mt-1.5 h-11 w-full rounded-xl border border-line-strong bg-surface shadow-e1 px-3 text-[0.9375rem] text-ink transition-colors placeholder:text-ink-subtle hover:border-ink-subtle focus:border-accent focus:outline-none disabled:opacity-60"
        {...input}
      />
      {hint && (
        <div id={hintId} className="mt-1.5 text-xs text-ink-subtle">
          {hint}
        </div>
      )}
    </div>
  );
}

export function FormError({ message }: { message: string | null }) {
  if (!message) return null;
  return (
    <p role="alert" className="flex items-start gap-2 border-l-2 border-danger bg-danger-soft px-3 py-2.5 text-sm text-danger">
      <AlertCircle className="mt-0.5 size-4 shrink-0" aria-hidden="true" />
      {message}
    </p>
  );
}

export function SubmitButton({ busy, children }: { busy: boolean; children: ReactNode }) {
  return (
    <button
      type="submit"
      disabled={busy}
      className="inline-flex h-11 w-full items-center justify-center gap-2 rounded-xl bg-ink shadow-e2 px-4 text-sm font-semibold text-canvas transition-colors hover:bg-ink/90 disabled:cursor-wait disabled:opacity-70"
    >
      {busy && <Loader2 className="size-4 animate-spin" aria-hidden="true" />}
      {children}
    </button>
  );
}
