# OpenCampus design system

**Bright Contemporary — intelligent, expressive, restrained.**

All tokens live in `frontend/src/styles/index.css`:

- `:root` holds raw `--oc-*` CSS variables (usable from any CSS).
- `@theme` maps them to Tailwind utilities (`bg-canvas`, `text-ink`,
  `border-line`, `font-display`, …). Change a value once, in `:root`.

## Colour

| Role            | Token                  | Use                                        |
| --------------- | ---------------------- | ------------------------------------------ |
| Canvas          | `--oc-canvas`          | page background (saturated sky, not white) |
| Sidebar         | `--oc-sidebar`         | periwinkle-tinted navigation surface       |
| Surface         | `--oc-surface`         | panels (kept near-white for reading)       |
| Sunken          | `--oc-surface-sunken`  | hover wells                                |
| Periwinkle      | `--oc-periwinkle`      | brand mark, supporting fills               |
| Lavender        | `--oc-lavender`        | reserved secondary tint                    |
| Ink             | `--oc-ink` (+ muted/subtle) | text, deep navy scale                 |
| Line            | `--oc-line` (+ strong) | 1px rules and borders                      |
| Accent          | `--oc-accent`          | interactive only: links, focus, active nav |
| Signal          | `--oc-signal`          | one warm highlight per view, brand door    |
| Status          | success / danger / pending (+ `-soft`) | state, never decoration    |
| Subject / section | `--oc-subject-{cobalt,teal,amber,rose,violet}` | identifies a subject across progress, schedule and assignments; also each dashboard section's accent |

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
- `.oc-blueprint` is the architectural motif: a faint 24/96px grid.
  `.oc-blueprint-wash` lays it over a periwinkle→lavender wash; use it only
  for hero surfaces (welcome, event illustration, sign-in panel).
- Section accents: `PanelHeader tone=…` adds a 4px top rule, a tinted band and
  a coloured dot. Progress = cobalt, today = teal, due soon = rose,
  campus = violet, event = signal. The welcome block is solid cobalt.

## Content density

Students skim on phones. Rules:

- One line of detail per item, at most. Relative dates ("Tomorrow"), not
  relative + absolute.
- No label that repeats the heading below it.
- Mark *exceptions*, not every state: only high priority gets a tag.
- Unavailable features share one "Coming soon" label per group, not one per item.
- Developer diagnostics (API status) render only in development builds.

## Mobile first

- Source order is the phone order: welcome (next class + due count) → today →
  due soon → progress → campus → event → assistant. Desktop rearranges the same
  grid with `lg:order-*` and column spans.
- Below 1024px a bottom tab bar (Home, Classes, Tasks, Campus, Menu) jumps to
  sections and highlights the one in view.
- Tap targets ≥44px; horizontal rows scroll inside themselves (`.oc-scroll-x`)
  and grid columns use `minmax(0,1fr)` so they never widen the page.
- Breakpoints: sidebar is fixed at ≥1024px (`lg`), a drawer below.
- Motion only for state changes (drawer, spinner); honours
  `prefers-reduced-motion`.
