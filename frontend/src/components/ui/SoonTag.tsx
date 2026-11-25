/** Marks a feature that is visible in the UI but not built yet. */
export function SoonTag({ label = "Soon", className = "" }: { label?: string; className?: string }) {
  return (
    <span
      className={`inline-flex shrink-0 items-center border border-line-strong px-1.5 py-px font-mono text-[0.625rem] font-medium tracking-[0.08em] text-ink-subtle uppercase ${className}`}
    >
      {label}
    </span>
  );
}
