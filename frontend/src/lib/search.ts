/** Normalised, case-insensitive substring search over visible dashboard text. */
export function normalise(text: string): string {
  return text.toLocaleLowerCase().trim();
}

export function matches(query: string, ...fields: (string | undefined)[]): boolean {
  const q = normalise(query);
  if (!q) return true;
  return fields.some((field) => field !== undefined && normalise(field).includes(q));
}
