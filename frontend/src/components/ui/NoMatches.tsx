export function NoMatches({ what }: { what: string }) {
  return <p className="px-5 py-6 text-sm text-ink-subtle sm:px-6">No {what} match your search.</p>;
}
