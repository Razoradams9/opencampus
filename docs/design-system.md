# OpenCampus design system

**Bold Contemporary** (evolved from "Bright Contemporary"): confident colour
blocking, editorial type, and graphics that carry information. Bold is not
busy: every graphic answers a question a student actually has.

All tokens live in `frontend/src/styles/index.css`:

- `:root` holds raw `--oc-*` CSS variables (usable from any CSS).
- `@theme` maps them to Tailwind utilities (`bg-canvas`, `text-ink`,
  `border-line`, `font-display`, …). Change a value once, in `:root`.

## Colour

**Light, multi-hue.** Near-white reading surfaces and deep navy ink; colour
comes from five hues, each owning a job and a region, so no single colour
dominates.

| Hue | Token | Owns |
| --- | ----- | ---- |
| Cobalt `#3550dc` | `--oc-accent`, `--oc-subject-cobalt` | interactive accent (links, focus, active tab), hero start, progress |
| Teal `#0b7f7a` | `--oc-subject-teal` | today / schedule |
| Orange `#c2410c` | `--oc-subject-amber` | subject tone; warm campus corner (with apricot surfaces) |
| Rose `#d02c5e` | `--oc-subject-rose` | due soon / tasks |
| Violet `#7442d6` | `--oc-subject-violet` | campus news, hero end, sidebar tint |

| Role | Token | Value |
| ---- | ----- | ----- |
| Canvas | `--oc-canvas` | `#f3f5fb` + four faint hue glows (cobalt, violet, peach, teal) |
| Surface / sunken | `--oc-surface` / `--oc-surface-sunken` | `#ffffff` / `#eef1f8` |
| Sidebar | `--oc-sidebar` | `#f1efff` (violet tint) |
| Hero | `--oc-hero` → `--oc-hero-light` | cobalt → violet gradient, white text |
| Progress panel | `--oc-lavender` | `#f3f0ff` |
| Event / campus | `--oc-apricot`, `--oc-apricot-soft`, `--oc-apricot-ink` | peach surfaces, burnt-orange text |
| Ink | `--oc-ink` / `-muted` / `-subtle` | `#141c3a` / `#4a5375` / `#5f6889` |
| Signal | `--oc-signal` | `#f26b3a`, graphics only |

**No dark fills.** Navy is for text only. Primary buttons and the skip link
are cobalt with white text; the active nav item is a white pill with cobalt
text; the logo tile is `--oc-accent-soft` with a cobalt arch; overlays are a
translucent cobalt blur.

Measured contrast: ink-subtle ≥4.8:1 on every surface (canvas 5.0, sidebar
4.8, surface 5.5); white on every subject tone 4.9–6.3:1 and on both hero
stops ≥6:1; apricot-ink on apricot 6.1:1. All text meets WCAG AA. Subject
tones are dark enough for white text (featured schedule block) and vivid
enough as marks on white.

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
| Study assistant | navy block, arch motif | none (planned feature) |
| Today | white card | **proportional day view**: block height = class length; hour grid; orange now-line; one filled class |
| Due soon | white card | **7-day workload strip**: each task as its subject's shape on its due day, hollow when done |
| Progress | **lavender colour block** | **lesson tracks**: one segment per lesson, big percentage numeral |
| Campus | no card: editorial list on the canvas | serif headlines, date column, category in colour |
| Event | **apricot poster** (warm counterweight) | oversized date numeral, hall illustration |

Headings sit **outside** their content as editorial titles (`SectionHeading`:
Fraunces 28–32px with a short coloured rule and a mono meta count).

### Subject identity
`SubjectMark` gives every subject a **shape and a colour** (cobalt circle,
teal square, amber triangle, rose diamond, violet hexagon) so subjects are
distinguishable without colour vision. Used in the hero, timetable, workload
strip, task rows and progress. Real (API) subjects get their tone from a
stable hash of the subject code (`toneFor` in `lib/academic/format.ts`), so a
subject keeps its colour and shape on every page and device.

### Real-data pages (M4)
- **Academics** and **Timetable** reuse `SectionHeading`, `.oc-panel` and
  `SubjectMark`; no new tokens.
- `DataState` (`Loading`, `LoadError` with retry, `Empty`) is the standard
  for every API-backed panel: never a blank box or a silent failure.
- `.oc-reveal`: 180 ms rise for content arriving from the API (disabled by
  reduced-motion like all motion).
- Timetable layout: one column per weekday on desktop (weekend shown only if
  it has classes), two columns on tablets, a single agenda column on phones
  with empty days hidden. Today's column uses the accent band; cancelled
  sessions keep their slot, struck through, with a text "Cancelled" label.
- Mobile tab bar: Home · Classes (timetable) · Courses (academics) · Tasks
  (dashboard section) · Menu. The active tab uses the accent colour.

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
