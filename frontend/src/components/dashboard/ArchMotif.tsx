/**
 * Concentric arches, derived from the OpenCampus mark: the brand's
 * architectural motif, drawn in thin strokes as a background accent.
 */
export function ArchMotif({ className = "" }: { className?: string }) {
  const arches = [40, 70, 100, 130, 160];
  return (
    <svg viewBox="0 0 360 220" className={className} aria-hidden="true" fill="none">
      {arches.map((r) => (
        <path key={r} d={`M${180 - r} 220V${220 - r * 0.55} a${r} ${r} 0 0 1 ${r * 2} 0V220`} stroke="currentColor" strokeWidth="1.25" />
      ))}
      <line x1="0" y1="219.5" x2="360" y2="219.5" stroke="currentColor" strokeWidth="1.25" />
    </svg>
  );
}
