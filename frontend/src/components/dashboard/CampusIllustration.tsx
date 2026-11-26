/**
 * Line drawing of a campus hall: pediment, colonnade and steps, with a
 * faint ground grid. Uses only design tokens so it follows the palette.
 */
import type React from "react";

export function CampusIllustration({ className = "" }: { className?: string }) {
  const columns = [70, 110, 150, 190, 230];
  return (
    <svg viewBox="0 0 300 180" className={className} role="img" aria-label="Line drawing of a campus hall">
      <g stroke="var(--oc-line-strong)" strokeWidth="0.75">
        {[150, 160, 170].map((y) => (
          <line key={y} x1="0" x2="300" y1={y} y2={y} pathLength={1} className="oc-draw" />
        ))}
      </g>
      <g fill="none" stroke="var(--oc-ink)" strokeWidth="1.5" strokeLinejoin="round">
        {/* Pediment */}
        <path d="M40 62 L150 22 L260 62 Z" pathLength={1} className="oc-draw" />
        <path d="M62 56 L150 33 L238 56" stroke="var(--oc-ink-subtle)" strokeWidth="1" pathLength={1} className="oc-draw" />
        {/* Entablature */}
        <rect x="40" y="62" width="220" height="12" pathLength={1} className="oc-draw" />
        {/* Columns */}
        {columns.map((x) => (
          <g key={x}>
            <rect x={x - 6} y="74" width="12" height="4" />
            <line x1={x - 4} x2={x - 4} y1="78" y2="130" pathLength={1} className="oc-draw" />
            <line x1={x + 4} x2={x + 4} y1="78" y2="130" pathLength={1} className="oc-draw" />
            <rect x={x - 6} y="130" width="12" height="4" />
          </g>
        ))}
        {/* Steps */}
        <path d="M34 134 H266 M28 141 H272 M22 148 H278" pathLength={1} className="oc-draw" />
      </g>
      {/* Lit doorway: the event's accent */}
      <rect x="143" y="96" width="14" height="34" fill="var(--oc-signal)" className="oc-enter" style={{ "--i": 14 } as React.CSSProperties} />
      <circle cx="150" cy="46" r="5" fill="none" stroke="var(--oc-signal)" strokeWidth="1.5" />
    </svg>
  );
}
