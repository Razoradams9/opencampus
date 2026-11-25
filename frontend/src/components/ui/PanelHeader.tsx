import type { ReactNode } from "react";
import type { SubjectTone } from "../../data/types";
import { toneStyle } from "../../lib/subjects";

interface PanelHeaderProps {
  id: string;
  index: string;
  title: string;
  /** Section accent: a top rule, a soft tinted band and a coloured index. */
  tone?: SubjectTone;
  /** Right-aligned meta content (counts, tags). */
  aside?: ReactNode;
}

/** Editorial section heading: index eyebrow, serif title, optional meta. */
export function PanelHeader({ id, index, title, tone, aside }: PanelHeaderProps) {
  return (
    <header
      style={tone ? toneStyle(tone) : undefined}
      className={`flex items-end justify-between gap-4 border-b border-line px-5 pt-4 pb-3 sm:px-6 ${
        tone ? "border-t-[3px] border-t-(--tone) bg-(--tone)/[0.07]" : ""
      }`}
    >
      <div>
        <p className={`oc-eyebrow ${tone ? "text-(--tone)" : ""}`}>{index}</p>
        <h2 id={id} className="mt-1 font-display text-xl font-medium tracking-tight">
          {title}
        </h2>
      </div>
      {aside && <div className="pb-0.5">{aside}</div>}
    </header>
  );
}
