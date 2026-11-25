import { normalise } from "../../lib/search";

/** Renders text with the first occurrence of the search query marked. */
export function Highlight({ text, query }: { text: string; query: string }) {
  const q = normalise(query);
  if (!q) return <>{text}</>;
  const index = text.toLocaleLowerCase().indexOf(q);
  if (index === -1) return <>{text}</>;
  return (
    <>
      {text.slice(0, index)}
      <mark className="oc-mark">{text.slice(index, index + q.length)}</mark>
      {text.slice(index + q.length)}
    </>
  );
}
