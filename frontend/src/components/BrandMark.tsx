/** OpenCampus logotype: an arch-and-door mark plus a two-weight wordmark. */
export function BrandMark() {
  return (
    <div className="flex items-center gap-2.5">
      <svg viewBox="0 0 32 32" className="size-8 shrink-0" aria-hidden="true">
        <rect width="32" height="32" rx="4" fill="var(--oc-accent-soft)" />
        <path d="M8 24V13l8-5 8 5v11" fill="none" stroke="var(--oc-accent)" strokeWidth="2" />
        <path d="M13 24v-6h6v6" fill="none" stroke="var(--oc-signal)" strokeWidth="2" />
      </svg>
      <span className="text-[1.0625rem] leading-none tracking-tight">
        <span className="font-display font-medium">Open</span>
        <span className="font-sans font-semibold">Campus</span>
      </span>
    </div>
  );
}
