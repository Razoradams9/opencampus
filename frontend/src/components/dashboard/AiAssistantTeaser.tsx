import { Sparkles } from "lucide-react";

const EXAMPLE_PROMPTS = [
  "Explain heap insertion step by step",
  "Quiz me on graph colouring",
  "Summarise this week's architecture notes",
];

/**
 * Planned-feature panel. Deliberately has no input or button: nothing here
 * is connected to an AI service.
 */
export function AiAssistantTeaser() {
  return (
    <section
      aria-labelledby="ai-title"
      className="relative flex flex-col overflow-hidden bg-ink px-6 pt-6 pb-7 text-canvas sm:px-7"
    >
      {/* Faint grid continues the blueprint motif in negative */}
      <div
        className="pointer-events-none absolute inset-0 opacity-[0.08]"
        style={{
          backgroundImage:
            "linear-gradient(to right, var(--oc-periwinkle) 1px, transparent 1px), linear-gradient(to bottom, var(--oc-periwinkle) 1px, transparent 1px)",
          backgroundSize: "32px 32px",
        }}
        aria-hidden="true"
      />

      <div className="relative flex items-center justify-between">
        <p className="font-mono text-[0.6875rem] font-medium tracking-[0.12em] text-periwinkle uppercase">
          Study assistant
        </p>
        <span className="border border-periwinkle/50 px-1.5 py-px font-mono text-[0.625rem] tracking-[0.08em] text-periwinkle uppercase">
          Planned
        </span>
      </div>

      <div className="relative mt-6 flex items-start gap-3">
        <Sparkles className="mt-1 size-5 shrink-0 text-signal" aria-hidden="true" />
        <h2 id="ai-title" className="font-display text-2xl leading-tight font-medium">
          A tutor that knows your courses.
        </h2>
      </div>
      <p className="relative mt-3 text-sm leading-relaxed text-periwinkle">
        Ask questions about your own notes and readings. Not available yet, and not connected to any AI service.
      </p>

      <p className="relative mt-6 font-mono text-[0.6875rem] tracking-[0.12em] text-periwinkle/80 uppercase">
        You'll be able to ask
      </p>
      <ul className="relative mt-2 space-y-1.5 text-sm text-canvas/90">
        {EXAMPLE_PROMPTS.map((prompt) => (
          <li key={prompt} className="border-l border-periwinkle/40 pl-3">
            {prompt}
          </li>
        ))}
      </ul>
    </section>
  );
}
