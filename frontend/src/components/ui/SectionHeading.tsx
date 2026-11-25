import type { ReactNode } from "react";

interface SectionHeadingProps {
  id: string;
  title: string;
  /** Short mono meta on the right: a count, a status. */
  meta?: ReactNode;
  /** Colour of the short rule before the title. */
  accent?: string;
  className?: string;
}

/** Editorial section heading that sits outside the content block. */
export function SectionHeading({ id, title, meta, accent = "var(--oc-ink)", className = "" }: SectionHeadingProps) {
  return (
    <div className={`mb-3 flex items-end justify-between gap-4 ${className}`}>
      <h2 id={id} className="flex items-center gap-3 font-display text-[1.75rem] leading-none font-medium tracking-tight sm:text-[2rem]">
        <span className="h-6 w-1.5 rounded-full" style={{ background: accent }} aria-hidden="true" />
        {title}
      </h2>
      {meta && <div className="pb-0.5 font-mono text-xs text-ink-muted">{meta}</div>}
    </div>
  );
}
