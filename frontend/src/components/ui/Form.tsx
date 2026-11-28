import { Loader2 } from "lucide-react";
import type { ButtonHTMLAttributes, InputHTMLAttributes, ReactNode, SelectHTMLAttributes, TextareaHTMLAttributes } from "react";

/** Form primitives for in-app editors (auth screens keep their own). */
const control =
  "mt-1.5 w-full rounded-xl border border-line-strong bg-surface px-3 text-[0.9375rem] text-ink shadow-e1 transition-colors placeholder:text-ink-subtle hover:border-ink-subtle focus:border-accent focus:outline-none disabled:opacity-60";

function Wrap({ id, label, hint, children }: { id: string; label: string; hint?: ReactNode; children: ReactNode }) {
  return (
    <div>
      <label htmlFor={id} className="block text-sm font-medium">
        {label}
      </label>
      {children}
      {hint && <p id={`${id}-hint`} className="mt-1 text-xs text-ink-subtle">{hint}</p>}
    </div>
  );
}

export function TextInput({ id, label, hint, ...props }: InputHTMLAttributes<HTMLInputElement> & { id: string; label: string; hint?: ReactNode }) {
  return (
    <Wrap id={id} label={label} hint={hint}>
      <input id={id} aria-describedby={hint ? `${id}-hint` : undefined} className={`${control} h-11`} {...props} />
    </Wrap>
  );
}

export function TextArea({ id, label, hint, ...props }: TextareaHTMLAttributes<HTMLTextAreaElement> & { id: string; label: string; hint?: ReactNode }) {
  return (
    <Wrap id={id} label={label} hint={hint}>
      <textarea id={id} aria-describedby={hint ? `${id}-hint` : undefined} className={`${control} min-h-28 py-2.5 leading-relaxed`} {...props} />
    </Wrap>
  );
}

export function Select({ id, label, hint, children, ...props }: SelectHTMLAttributes<HTMLSelectElement> & { id: string; label: string; hint?: ReactNode }) {
  return (
    <Wrap id={id} label={label} hint={hint}>
      <select id={id} className={`${control} h-11`} {...props}>
        {children}
      </select>
    </Wrap>
  );
}

type Variant = "primary" | "secondary" | "ghost" | "danger";
const VARIANTS: Record<Variant, string> = {
  primary: "bg-accent text-white shadow-e1 hover:brightness-110",
  secondary: "bg-surface text-ink ring-1 ring-line-strong hover:bg-sunken",
  ghost: "text-accent hover:bg-accent-soft",
  danger: "text-danger hover:bg-danger-soft",
};

export function Button({
  variant = "secondary",
  busy = false,
  icon,
  children,
  className = "",
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: Variant; busy?: boolean; icon?: ReactNode }) {
  return (
    <button
      type="button"
      disabled={busy || props.disabled}
      className={`inline-flex h-10 items-center justify-center gap-2 rounded-xl px-4 text-sm font-semibold transition-[filter,background-color] disabled:cursor-not-allowed disabled:opacity-60 ${VARIANTS[variant]} ${className}`}
      {...props}
    >
      {busy ? <Loader2 className="size-4 animate-spin" aria-hidden="true" /> : icon}
      {children}
    </button>
  );
}

const STATUS_STYLE: Record<string, string> = {
  draft: "bg-pending-soft text-pending",
  published: "bg-success-soft text-success",
  archived: "bg-sunken text-ink-subtle",
};

/** Lifecycle chip for authored content; text, not colour alone. */
export function StatusChip({ status }: { status: string }) {
  return (
    <span className={`inline-flex shrink-0 items-center rounded-full px-2 py-0.5 text-[0.6875rem] font-semibold capitalize ${STATUS_STYLE[status] ?? "bg-sunken text-ink-muted"}`}>
      {status}
    </span>
  );
}
