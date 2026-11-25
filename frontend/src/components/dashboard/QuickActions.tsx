import { BrainCircuit, CalendarRange, FileUp, MessageSquareText } from "lucide-react";
import type { LucideIcon } from "lucide-react";
import type { SubjectTone } from "../../data/types";
import { toneStyle } from "../../lib/subjects";

interface QuickAction {
  label: string;
  icon: LucideIcon;
  tone: SubjectTone;
}

const ACTIONS: QuickAction[] = [
  { label: "Upload notes", icon: FileUp, tone: "cobalt" },
  { label: "Generate quiz", icon: BrainCircuit, tone: "teal" },
  { label: "Plan study", icon: CalendarRange, tone: "rose" },
  { label: "Ask AI", icon: MessageSquareText, tone: "violet" },
];

/**
 * Entry points for upcoming tools: disabled, with one shared "coming soon"
 * label instead of a tag on every button. Swipeable row on phones.
 */
export function QuickActions() {
  return (
    <section aria-labelledby="quick-actions-title" className="h-full">
      <div className="mb-2 flex items-baseline justify-between">
        <h2 id="quick-actions-title" className="oc-eyebrow">
          Quick actions
        </h2>
        <p className="font-mono text-[0.6875rem] tracking-[0.08em] text-ink-subtle uppercase">Coming soon</p>
      </div>
      <ul className="oc-scroll-x -mx-4 flex gap-2 px-4 sm:mx-0 sm:grid sm:grid-cols-4 sm:px-0">
        {ACTIONS.map(({ label, icon: Icon, tone }) => (
          <li key={label} style={toneStyle(tone)} className="shrink-0">
            <button
              type="button"
              disabled
              aria-describedby="quick-actions-title"
              className="flex h-12 w-full cursor-not-allowed items-center gap-2.5 border border-line bg-surface/80 pr-4 pl-2 text-sm font-medium whitespace-nowrap text-ink-muted"
            >
              <span className="grid size-8 place-items-center bg-(--tone)/15 text-(--tone)" aria-hidden="true">
                <Icon className="size-4" />
              </span>
              {label}
            </button>
          </li>
        ))}
      </ul>
    </section>
  );
}
