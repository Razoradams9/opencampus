# OpenCampus design system (M0)

**Bright Contemporary — intelligent, expressive, restrained.**

All tokens live in `frontend/src/styles/index.css`:

- `:root` holds raw `--oc-*` CSS variables (usable from any CSS).
- `@theme` maps them to Tailwind utilities (`bg-canvas`, `text-ink`,
  `border-line`, `font-display`, …). Change a value once, in `:root`.

## Colour

| Role            | Token                  | Use                                        |
| --------------- | ---------------------- | ------------------------------------------ |
| Canvas          | `--oc-canvas`          | page background (pale sky, not white)      |
| Surface         | `--oc-surface`         | panels, sidebar                            |
| Sunken          | `--oc-surface-sunken`  | hover wells                                |
| Periwinkle      | `--oc-periwinkle`      | brand mark, supporting fills               |
| Lavender        | `--oc-lavender`        | reserved secondary tint                    |
| Ink             | `--oc-ink` (+ muted/subtle) | text, deep navy scale                 |
| Line            | `--oc-line` (+ strong) | 1px rules and borders                      |
| Accent          | `--oc-accent`          | interactive only: links, focus, active nav |
| Signal          | `--oc-signal`          | one warm highlight per view, brand door    |
| Status          | success / danger / pending (+ `-soft`) | state, never decoration    |

## Type

- **Display:** Fraunces (headings, panel titles).
- **Text:** Geist.
- **Data / labels:** Geist Mono, via `.oc-eyebrow` for indices and metadata.

## Layout rules

- Panels use 1px borders and small radii (`--oc-radius`, 6px), no drop shadows.
- Asymmetric 12-column grid on desktop (e.g. 7/5 splits); stacks on mobile.
- Sections are indexed editorially (`01 — Overview`, `2.1`).
- `.oc-blueprint` is the single architectural motif: a faint 24/96px grid,
  used once per view.
- Breakpoints: sidebar is fixed at ≥1024px (`lg`), a drawer below.
- Motion only for state changes (drawer, spinner); honours
  `prefers-reduced-motion`.
