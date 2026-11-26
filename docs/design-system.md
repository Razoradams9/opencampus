# OpenCampus design system

**Bold Academic Editorial + Interactive Motion** (evolved from Bold
Contemporary): confident colour blocking, editorial type, graphics that carry
information, and fast, purposeful motion. Bold is not busy: every graphic
answers a question a student actually has, and every animation explains a
change or an arrival.

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

- Cards (`.oc-panel`) are rounded (`--oc-radius-card`, 14px) and raised one
  level (`--oc-shadow-1` + a lit top edge). See *Depth* below.
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

## Depth

Follows Material's elevation model: shadow size tracks height, one light
source from above, and a shadow never appears without a reason to be higher.

| Level | Token            | Used for |
| ----- | ---------------- | -------- |
| 0     | canvas           | page, with soft radial "daylight" from the top-left |
| 1     | `--oc-shadow-1`  | cards, quick actions, inputs, institution switcher |
| 2     | `--oc-shadow-2`  | the one thing that matters now: current class, next-class chip, active nav, AI and date blocks |
| 3     | `--oc-shadow-3`  | floating UI: bottom tab bar, menus, notifications |

Shadows are navy-tinted, never grey. `.oc-lift` adds a 1px lift on hover.

## Calm by default

Opening the portal should not feel like an alarm. Rules, with the strength of
the evidence behind each:

- **Show the next step, disclose the rest.** Due soon shows the 3 nearest
  tasks; "Show all N" reveals the rest and always states how many
  (progressive disclosure; moderate evidence, NN/g / Carroll).
- **Red means overdue, nothing else.** Today/tomorrow use the accent blue;
  priority is a soft amber "Priority" chip (red-and-anxiety research is
  mixed, so red is kept for the one case that truly needs it).
- **Frame workload as progress.** "2 of 5 tasks done" with a bar, "All caught
  up" when finished, a small check animation on completion (endowed-progress /
  goal-gradient findings).
- **One loud thing at a time.** Only the current (or next) class is filled;
  the other upcoming class is a soft tint.
- **No counters where a signal will do.** The notification bell shows a dot.
- Motion is short, purposeful and disabled under `prefers-reduced-motion`.

## Bold Contemporary (dashboard)

### Composition
Sections are **not** all the same card. Each has its own treatment:

| Section | Surface | Graphic (what it tells you) |
| ------- | ------- | --------------------------- |
| Welcome | cobalt slab, concentric-arch motif | next-class ticket; **day rail**: today's classes as segments with an orange "now" marker (load and gaps) |
| Study assistant | **periwinkle block**, static node-graph mark, "Not connected yet" status | none (planned feature) |
| Today | **navy block** | **proportional day view**: block height = class length; hour grid; orange now-line; one filled class; tinted navy blocks per subject |
| Due soon | white card | **7-day workload strip**: each task as its subject's shape on its due day, hollow when done |
| Progress | **lavender colour block** | **arch chart**: concentric semicircles (the brand arch), one arc per course filled to its progress, average numeral in the centre; lesson tracks as the legend |
| Campus | no card: editorial list on the canvas | serif headlines, date column, category in colour |
| Event | **apricot poster** (warm counterweight) | oversized date numeral, hall illustration |

Headings sit **outside** their content as editorial titles (`SectionHeading`:
Fraunces 28–32px with a short coloured rule and a mono meta count).

### Subject identity
`SubjectMark` gives every subject a **shape and a colour** (cobalt circle,
teal square, amber triangle, rose diamond, violet hexagon) so subjects are
distinguishable without colour vision. Used in the hero, timetable, workload
strip, task rows and progress.

### Colour blocking
Cobalt (hero), navy (assistant), lavender (progress), apricot (event) and
white (operational lists) on the sky canvas. Apricot uses `--oc-apricot-ink`
(#a3401d, 5.2:1) for small text; `--oc-signal-strong` only for large numerals.

### Type scale
Hero greeting 40px → 68px (Fraunces, tight leading); section titles 28–32px;
data numerals (times, dates, percentages) in Fraunces with tabular figures;
body 15px Geist; metadata 11–12px Geist Mono. Never below 11px.

### Motifs
`ArchMotif` (concentric arches from the logo) is the single decorative
element, drawn at 13–14% opacity on dark surfaces only.

## Motion system

Fast, precise, intentional. CSS only (no animation library: every sequence
here is a single entrance or state change, which CSS keyframes and
transitions handle with zero bundle cost).

### Tokens (`index.css`)

| Token | Value | Use |
| ----- | ----- | --- |
| `--oc-dur-instant` | 110ms | press feedback |
| `--oc-dur-micro` | 160ms | hovers, toggles, menus opening |
| `--oc-dur-ui` | 220ms | state changes, drawer, tab indicator, strike line |
| `--oc-dur-enter` | 420ms | first-paint entrances, bar fills |
| `--oc-ease-out` | cubic-bezier(0,0,.2,1) | things arriving |
| `--oc-ease-standard` | cubic-bezier(.4,0,.2,1) | things changing |
| `--oc-ease-emphasized` | cubic-bezier(.2,0,0,1) | chart fills, hero moments |
| `--oc-stagger` | 55ms | step between staggered items (`--i`) |

### Utilities

`.oc-enter` (fade + 12px rise), `.oc-enter-side` (fade + 16px from the right,
for side panels), `.oc-press` (scale .97 on press, real buttons only),
`.oc-nudge` (arrow moves 0.2em when its link/button is hovered or focused),
`.oc-pop-in` (menus open from their anchor), `.oc-grow-x` (bars fill from
their start edge), `.oc-arc` (SVG arc fills to `--p`), `.oc-draw` /
`.oc-draw-quick` (SVG strokes draw themselves; `pathLength="1"`),
`.oc-state` (colour/opacity transitions for live state changes),
`.oc-lift` (1px hover lift).

### Where motion is used

- Dashboard sections enter in phone order, 55ms apart; the assistant panel
  enters from the side on desktop.
- Hero: greeting, then next-class ticket; day-rail segments grow in order.
- Timetable blocks cascade in; class states (past/now/next) cross-fade as the
  clock moves (`useNow` re-renders every minute).
- Arch chart arcs and lesson tracks fill once.
- Task tick: checkmark draws (220ms), strike line sweeps across the title,
  box pops once (no bounce loop).
- Event illustration draws itself once.
- Mobile tab bar: one indicator slides between tabs.
- Notifications and institution menus open from their anchor.

### Rules

- Animate `transform`, `opacity` and SVG stroke offsets only; never layout
  properties. (Measured: 0 frames over 34ms during the entrance with 4x CPU
  throttling on a phone viewport; no layout shift.)
- Nothing loops or runs in the background. No parallax. No bounce beyond a
  single small overshoot.
- Motion never carries information on its own: every final state is
  readable without it.
- `prefers-reduced-motion: reduce`: all animations and transitions resolve
  instantly, stagger delays are removed, smooth scrolling is off.
- Hover effects only on things that are interactive; disabled controls do not
  react.
