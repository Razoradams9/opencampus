import type { CampusUpdate, UpdateCategory } from "../../data/types";
import { formatRelativeDay } from "../../lib/dates";
import { Highlight } from "../ui/Highlight";
import { NoMatches } from "../ui/NoMatches";
import { PanelHeader } from "../ui/PanelHeader";

interface CampusUpdatesProps {
  updates: CampusUpdate[];
  today: Date;
  query: string;
}

const CATEGORY_STYLE: Record<UpdateCategory, string> = {
  Academic: "text-accent",
  Facilities: "text-subject-teal",
  IT: "text-subject-amber",
  "Campus life": "text-subject-rose",
};

export function CampusUpdates({ updates, today, query }: CampusUpdatesProps) {
  return (
    <section aria-labelledby="updates-title" className="oc-panel flex flex-col">
      <PanelHeader id="updates-title" index="Campus" title="Campus updates" />

      {updates.length === 0 ? (
        <NoMatches what="updates" />
      ) : (
        <ul className="divide-y divide-line">
          {updates.map((u) => (
            <li key={u.id} className={`relative px-5 py-4 sm:px-6 ${u.important ? "bg-lavender/35" : ""}`}>
              {u.important && <span className="absolute inset-y-0 left-0 w-0.5 bg-accent" aria-hidden="true" />}
              <article>
                <div className="flex items-center justify-between gap-3">
                  <p className={`font-mono text-[0.6875rem] font-medium tracking-[0.08em] uppercase ${CATEGORY_STYLE[u.category]}`}>
                    <Highlight text={u.category} query={query} />
                    {u.important && <span className="ml-2 text-ink">· Important</span>}
                  </p>
                  <time dateTime={u.date.toISOString().slice(0, 10)} className="shrink-0 font-mono text-xs text-ink-subtle">
                    {formatRelativeDay(u.date, today)}
                  </time>
                </div>
                <h3 className="mt-1.5 text-sm font-semibold">
                  <Highlight text={u.title} query={query} />
                </h3>
                <p className="mt-0.5 text-sm leading-relaxed text-ink-muted">
                  <Highlight text={u.body} query={query} />
                </p>
              </article>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
