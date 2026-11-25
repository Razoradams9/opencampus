import type { ReactNode } from "react";

interface PanelHeaderProps {
  id: string;
  index: string;
  title: string;
  /** Right-aligned meta content (counts, tags). */
  aside?: ReactNode;
}

/** Editorial section heading: index eyebrow, serif title, optional meta. */
export function PanelHeader({ id, index, title, aside }: PanelHeaderProps) {
  return (
    <header className="flex items-end justify-between gap-4 border-b border-line px-5 pt-4 pb-3 sm:px-6">
      <div>
        <p className="oc-eyebrow">{index}</p>
        <h2 id={id} className="mt-1 font-display text-xl font-medium tracking-tight">
          {title}
        </h2>
      </div>
      {aside && <div className="pb-0.5">{aside}</div>}
    </header>
  );
}
