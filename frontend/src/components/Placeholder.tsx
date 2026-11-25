import type { LucideIcon } from "lucide-react";

interface PlaceholderProps {
  index: string;
  title: string;
  description: string;
  icon: LucideIcon;
  className?: string;
}

/** Clearly-labelled slot for a dashboard module that has not been built yet. */
export function Placeholder({ index, title, description, icon: Icon, className = "" }: PlaceholderProps) {
  return (
    <section className={`flex flex-col border border-line bg-surface/70 ${className}`} aria-label={title}>
      <header className="flex items-baseline justify-between border-b border-line px-5 py-3">
        <h3 className="font-display text-lg font-medium">{title}</h3>
        <span className="oc-eyebrow">{index}</span>
      </header>
      <div className="flex flex-1 items-start gap-4 px-5 py-6">
        <span className="grid size-9 shrink-0 place-items-center border border-line-strong border-dashed text-ink-subtle">
          <Icon className="size-4" />
        </span>
        <div>
          <p className="text-sm text-ink-muted">{description}</p>
          <p className="oc-eyebrow mt-3">Not built yet</p>
        </div>
      </div>
    </section>
  );
}
