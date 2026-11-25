# OpenCampus design system

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
| Subject         | `--oc-subject-{cobalt,teal,amber,rose}` | identifies one subject across progress, schedule and assignments |

All text colours meet WCAG AA (≥4.5:1) on canvas and surface; `--oc-signal`
is for graphics only, never text.

## Type

- **Display:** Fraunces (headings, panel titles).
- **Text:** Geist.
- **Data / labels:** Geist Mono, via `.oc-eyebrow` for indices and metadata.

## Layout rules

- Panels (`.oc-panel`) are flat with 1px borders and square corners; no drop
  shadows except the floating notifications panel.
- Each panel opens with `PanelHeader`: mono index eyebrow + serif title.
- Deliberate variation: the AI teaser is the one inverted (navy) block; quick
  actions are a ruled strip, not cards; the event pairs text with a line
  illustration.
- Unavailable features: disabled control + `SoonTag` (or "Planned"), never a
  control that silently does nothing.
- Priority and state are always shown as text as well as colour.
- Asymmetric 12-column grid on desktop (e.g. 7/5 splits); stacks on mobile.
- Sections are indexed editorially (`01 — Overview`, `2.1`).
- `.oc-blueprint` is the single architectural motif: a faint 24/96px grid,
  used once per view.
- Breakpoints: sidebar is fixed at ≥1024px (`lg`), a drawer below.
- Motion only for state changes (drawer, spinner); honours
  `prefers-reduced-motion`.
