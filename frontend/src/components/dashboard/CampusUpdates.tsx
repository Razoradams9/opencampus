import type { CampusUpdate, UpdateCategory } from "../../data/types";
import { formatRelativeDay } from "../../lib/dates";
import { Highlight } from "../ui/Highlight";
import { NoMatches } from "../ui/NoMatches";
import { SectionHeading } from "../ui/SectionHeading";

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

/** Editorial headline list set on a warm panel. */
export function CampusUpdates({ updates, today, query }: CampusUpdatesProps) {
  return (
    <section id="campus" aria-labelledby="updates-title" className="flex h-full scroll-mt-24 flex-col">
      <SectionHeading id="updates-title" title="Campus" accent="var(--oc-subject-violet)" />

      {updates.length === 0 ? (
        <NoMatches what="updates" />
      ) : (
        <ul className="rounded-card bg-apricot-soft p-4 sm:p-5">
          {updates.map((u) => (
            <li key={u.id} className="grid grid-cols-[4.25rem_1fr] gap-3 border-b border-ink/10 py-3.5 first:pt-0 last:border-0 last:pb-0">
              <time dateTime={u.date.toISOString().slice(0, 10)} className="pt-0.5 font-mono text-xs text-ink-muted">
                {formatRelativeDay(u.date, today)}
              </time>
              <div className="min-w-0">
                <p className="flex items-center gap-2 text-[0.6875rem] font-semibold tracking-wide uppercase">
                  <span className={CATEGORY_STYLE[u.category]}>
                    <Highlight text={u.category} query={query} />
                  </span>
                  {u.important && (
                    <span
                      className="size-1.5 rounded-full bg-subject-violet"
                      aria-hidden="true"
                      title="Important"
                    />
                  )}
                  {u.important && <span className="sr-only">Important</span>}
                </p>
                <h3 className="mt-1 font-display text-[1.1875rem] leading-snug font-medium tracking-tight">
                  <Highlight text={u.title} query={query} />
                </h3>
              </div>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
