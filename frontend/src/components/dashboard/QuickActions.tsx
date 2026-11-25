import { BrainCircuit, CalendarRange, FileUp, MessageSquareText } from "lucide-react";
import type { LucideIcon } from "lucide-react";
import type { SubjectTone } from "../../data/types";
import { toneStyle } from "../../lib/subjects";
import { SoonTag } from "../ui/SoonTag";

interface QuickAction {
  label: string;
  hint: string;
  icon: LucideIcon;
  tone: SubjectTone;
}

const ACTIONS: QuickAction[] = [
  { label: "Upload notes", hint: "Add lecture notes to a subject", icon: FileUp, tone: "cobalt" },
  { label: "Generate quiz", hint: "Practise from your notes", icon: BrainCircuit, tone: "teal" },
  { label: "Plan study", hint: "Block time around deadlines", icon: CalendarRange, tone: "rose" },
  { label: "Ask AI", hint: "Get help with a concept", icon: MessageSquareText, tone: "violet" },
];

/**
 * Entry points for upcoming tools. They are rendered as disabled buttons so
 * they are announced as unavailable and cannot be mistaken for working actions.
 */
export function QuickActions() {
  return (
    <section aria-labelledby="quick-actions-title">
      <div className="mb-3 flex items-baseline justify-between">
        <h2 id="quick-actions-title" className="oc-eyebrow">
          Quick actions
        </h2>
        <p className="text-xs text-ink-subtle">Arriving in later releases</p>
      </div>
      <ul className="grid grid-cols-2 border-t border-l border-line lg:grid-cols-4">
        {ACTIONS.map(({ label, hint, icon: Icon, tone }) => (
          <li key={label} className="border-r border-b border-line" style={toneStyle(tone)}>
            <button
              type="button"
              disabled
              aria-describedby="quick-actions-title"
              className="flex h-full w-full cursor-not-allowed flex-col items-start gap-3 bg-surface/75 p-4 text-left sm:p-5"
            >
              <span className="flex w-full items-center justify-between">
                <span className="grid size-9 place-items-center bg-(--tone)/12 text-(--tone)" aria-hidden="true">
                  <Icon className="size-[1.125rem]" />
                </span>
                <SoonTag />
              </span>
              <span>
                <span className="block text-sm font-semibold text-ink-muted">{label}</span>
                <span className="mt-0.5 block text-xs text-ink-subtle">{hint}</span>
              </span>
            </button>
          </li>
        ))}
      </ul>
    </section>
  );
}
