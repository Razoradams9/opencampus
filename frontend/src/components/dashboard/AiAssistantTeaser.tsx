import { Sparkles } from "lucide-react";

/** Planned feature. No input and no button: nothing here is connected to AI. */
export function AiAssistantTeaser() {
  return (
    <section aria-labelledby="ai-title" className="relative flex h-full flex-col justify-between gap-4 overflow-hidden bg-ink px-5 py-5 text-white sm:px-6">
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
        <span className="grid size-10 place-items-center bg-white/10">
          <Sparkles className="size-5 text-signal" aria-hidden="true" />
        </span>
        <span className="border border-periwinkle/60 px-1.5 py-px font-mono text-[0.625rem] tracking-[0.08em] text-periwinkle uppercase">
          Planned
        </span>
      </div>
      <div className="relative">
        <h2 id="ai-title" className="font-display text-xl leading-tight font-medium sm:text-2xl">
          Study assistant
        </h2>
        <p className="mt-1 text-sm text-periwinkle">A tutor that knows your courses. Not connected yet.</p>
      </div>
    </section>
  );
}
