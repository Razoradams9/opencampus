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
  Academic: "bg-accent-soft text-accent",
  Facilities: "bg-subject-teal/12 text-subject-teal",
  IT: "bg-subject-amber/12 text-subject-amber",
  "Campus life": "bg-subject-rose/12 text-subject-rose",
};

/** Headlines only: one line each, the detail belongs on a future update page. */
export function CampusUpdates({ updates, today, query }: CampusUpdatesProps) {
  return (
    <section id="campus" aria-labelledby="updates-title" className="oc-panel flex h-full scroll-mt-24 flex-col">
      <PanelHeader id="updates-title" title="Campus" tone="violet" />

      {updates.length === 0 ? (
        <NoMatches what="updates" />
      ) : (
        <ul className="divide-y divide-line">
          {updates.map((u) => (
            <li key={u.id} className="relative px-4 py-3 sm:px-5">
              {u.important && <span className="absolute inset-y-2 left-0 w-1 rounded-r-full bg-subject-violet" aria-hidden="true" />}
              <div className="flex items-center gap-2 text-[0.6875rem]">
                <span className={`rounded-full px-2 py-px font-medium ${CATEGORY_STYLE[u.category]}`}>
                  <Highlight text={u.category} query={query} />
                </span>
                {u.important && <span className="font-semibold text-subject-violet">Important</span>}
                <time dateTime={u.date.toISOString().slice(0, 10)} className="ml-auto font-mono text-ink-subtle">
                  {formatRelativeDay(u.date, today)}
                </time>
              </div>
              <h3 className="mt-1.5 text-[0.9375rem] leading-snug font-medium">
                <Highlight text={u.title} query={query} />
              </h3>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
