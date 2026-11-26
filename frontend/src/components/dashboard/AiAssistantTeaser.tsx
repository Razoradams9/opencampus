import { ArchMotif } from "./ArchMotif";

/** Static node-graph mark: the assistant's own identity (no motion, no fake activity). */
function AssistantMark() {
  const nodes: [number, number][] = [
    [6, 6], [20, 4], [34, 9], [10, 20], [26, 18], [38, 26], [8, 34], [22, 32],
  ];
  const links: [number, number][] = [[0, 1], [1, 2], [0, 3], [1, 4], [3, 4], [4, 5], [3, 6], [4, 7], [6, 7], [2, 5]];
  return (
    <svg viewBox="0 0 44 40" className="h-10 w-11" aria-hidden="true">
      {links.map(([a, b]) => (
        <line key={`${a}-${b}`} x1={nodes[a][0]} y1={nodes[a][1]} x2={nodes[b][0]} y2={nodes[b][1]} stroke="var(--oc-ink)" strokeOpacity="0.35" strokeWidth="1.25" />
      ))}
      {nodes.map(([x, y], i) => (
        <circle key={i} cx={x} cy={y} r={i === 4 ? 3.5 : 2.25} fill={i === 4 ? "var(--oc-signal)" : "var(--oc-ink)"} />
      ))}
    </svg>
  );
}

/** Planned feature. No input and no button: nothing here is connected to AI. */
export function AiAssistantTeaser() {
  return (
    <section
      aria-labelledby="ai-title"
      className="relative flex h-full flex-col justify-between gap-6 overflow-hidden rounded-card bg-periwinkle px-5 py-5 text-ink shadow-e1 sm:px-6"
    >
      <ArchMotif className="pointer-events-none absolute -right-16 -bottom-1 w-[20rem] text-ink/[0.08]" />
      <div className="relative flex items-start justify-between">
        <AssistantMark />
        <span className="rounded-full border border-ink/30 px-2 py-0.5 font-mono text-[0.625rem] font-medium tracking-[0.08em] uppercase">
          Planned
        </span>
      </div>
      <div className="relative">
        <h2 id="ai-title" className="font-display text-[1.75rem] leading-tight font-medium sm:text-[2rem]">
          Study assistant
        </h2>
        <p className="mt-1 text-sm text-ink">A tutor that knows your courses.</p>
        <p className="mt-3 inline-flex items-center gap-2 rounded-full bg-white/50 px-2.5 py-1 text-xs font-medium">
          <span className="size-2 rounded-full border-2 border-ink" aria-hidden="true" />
          Not connected yet
        </p>
      </div>
    </section>
  );
}
