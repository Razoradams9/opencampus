import type { ReactNode } from "react";
import type { SubjectTone } from "../../data/types";
import { toneStyle } from "../../lib/subjects";

interface PanelHeaderProps {
  id: string;
  title: string;
  /** Section accent: top rule, tinted band and a coloured marker. */
  tone?: SubjectTone;
  /** Right-aligned meta (a count, a tag). Keep it short. */
  aside?: ReactNode;
}

export function PanelHeader({ id, title, tone, aside }: PanelHeaderProps) {
  return (
    <header
      style={tone ? toneStyle(tone) : undefined}
      className={`flex items-center justify-between gap-4 border-b border-line/70 px-4 py-3 sm:px-5 ${
        tone ? "border-t-[3px] border-t-(--tone) bg-(--tone)/[0.09]" : ""
      }`}
    >
      <h2 id={id} className="flex items-center gap-2 font-display text-lg font-medium tracking-tight sm:text-xl">
        {tone && <span className="size-2 rounded-full bg-(--tone)" aria-hidden="true" />}
        {title}
      </h2>
      {aside && <div className="text-xs text-ink-subtle">{aside}</div>}
    </header>
  );
}
