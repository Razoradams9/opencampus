# Three-color palette and dashboard declutter

This change replaces the monochrome blue-dominant palette with a deliberate three-hue composition and strips approximately two-thirds of the dashboard's visual noise. The CSS token layer is reassigned to three hue families — slate-navy for the main canvas and content cards, muted sage-teal for structural/identity regions (sidebar, hero, progress panel), and warm sand for the campus-life corner (event card, updates strip). Concurrently, five components are deleted outright (AiAssistantTeaser, QuickActions, WeekLoad, plus the disabled Continue button and the Sample data pill), the sidebar's coming-soon list drops from seven items to three, and the search banner is tightened. The design approach maps hues to spatial regions rather than to component types, so the three families read as a composition rather than random coloring.

**Watch for:** No `code-report.md` exists — the coder's report file is absent; build evidence was inferred from dist artifacts (timestamped 21:50:43, 85 seconds before the commit, containing all five new hue hexes and none of the old palette, meaning `tsc --noEmit && vite build` passed on the final source). The `--oc-ink-subtle` token is documented as 5.0:1 on `--oc-surface` and 4.6:1 on the sage panel — the sage panel value sits at the 4.5:1 WCAG floor with no margin.

**Verdict**: APPROVED

---

## High-level view

The token layer drives all three families off `:root` custom properties with no component-level inline colors, so the mapping is enforced globally. The body background uses exactly two radial gradients — a sage glow anchored top-left over the sidebar/hero band, and a faint warm glow bottom-right over the campus corner — reinforcing the spatial composition without adding new CSS rules.

The declutter is structural: five full components deleted, not hidden. The Dashboard grid loses three slots (QuickActions, AiAssistantTeaser, WeekLoad section); in their place is one `oc-eyebrow` text line. The sidebar's seven disabled items become three. Priority badges, the Sample data pill, the tasks progress bar, the disabled Continue button, and the disabled Palette button are all gone. The result is fewer interactive affordances the student has to process and dismiss.

Protected elements are intact: the assignment checkbox toggle, the schedule "now" indicator (DayRail preserved, TodaySchedule untouched), all `aria-*`/`role` attributes, search and the Clear button, `NoMatches` empty states, and the responsive 12-column grid. The search banner change merges the count and Clear action into one line without re-displaying the query string — simpler and no functionality lost.

The `--oc-ink-subtle` token sits at the minimum WCAG AA threshold (4.6:1) on the sage progress panel. This is confirmed in the token comment in index.css. Body copy on the sage panel should use `--oc-ink-muted` (5.9:1) instead; `--oc-ink-subtle` is safe only for labels and secondary metadata on that surface.

---

<details>
<summary>Issues (2)</summary>

1. **No code-report.md** — The coder's report file specified in the task (`frontend/.agents/tasks/code-report.md`) does not exist. Build evidence is inferred from the dist timestamp and compiled CSS content rather than an explicit build log. The coder should write the report or the workflow should not mark this path as the evidence location if the agent logs elsewhere.

2. **`--oc-ink-subtle` at WCAG floor on sage panel** — `#7d92b8` on `#1c2b27` (AcademicProgress panel) computes to approximately 4.6:1, confirmed by the token comment. Any body-copy text using `text-ink-subtle` on this surface is one rounding step from failure. Use `text-ink-muted` for paragraph-weight text on the sage panel; reserve `text-ink-subtle` for labels, timestamps, and secondary metadata only.

</details>

<details>
<summary>Details</summary>

## `--oc-ink-subtle` contrast floor on sage surfaces

`--oc-ink-subtle: #7d92b8` against `--oc-lavender: #1c2b27` (AcademicProgress panel background) is approximately 4.6:1 — confirmed by the in-code token comment that explicitly notes "use ink-muted for body copy on sage." The token comment is advisory only. The LessonTrack component uses `text-ink-subtle` for the progress-bar percentage label; that is small body-weight text at the WCAG AA floor. Any future body-copy text added to the sage panel using `text-ink-subtle` would fail AA.

## Declutter verification

AiAssistantTeaser, QuickActions, and WeekLoad are confirmed deleted: source files absent from `src/components/dashboard/`, no references remain in any `.tsx` or `.ts` file, and neither name appears in the compiled bundle. The "Important" word in CampusUpdates is replaced by a bare dot with a `sr-only` span, preserving screen-reader accessibility.

</details>

---

<details>
<summary>File map</summary>

| File | What changed |
|---|---|
| `src/styles/index.css` | All token values reassigned to three hue families; body background to two new radials; `.oc-blueprint-wash` hardcoded stops retuned to sage; `--oc-apricot-soft` token + `@theme` mapping added |
| `src/pages/Dashboard.tsx` | Removed AiAssistantTeaser and QuickActions imports/slots; removed `tasksDone`/`featured` computations and props; renumbered grid orders; simplified search banner |
| `src/components/Sidebar.tsx` | UPCOMING array reduced from 7 to 3; four icon imports removed |
| `src/components/TopBar.tsx` | Disabled Palette button removed; Palette import removed |
| `src/components/dashboard/WelcomeSection.tsx` | Sample data pill removed; tasks progress bar removed; ArrowRight and "Up next" eyebrow label removed; `tasksDone`/`tasksTotal` props dropped |
| `src/components/dashboard/AssignmentList.tsx` | WeekLoad strip removed; Priority badge (both branches) removed |
| `src/components/dashboard/AcademicProgress.tsx` | Featured "Up next" card with disabled Continue button removed; `featured` prop removed; ArrowRight import removed |
| `src/components/dashboard/CampusUpdates.tsx` | List wrapped in warm `bg-apricot-soft` panel; "Important" text replaced with dot + sr-only span |
| `src/components/dashboard/AiAssistantTeaser.tsx` | Deleted |
| `src/components/dashboard/QuickActions.tsx` | Deleted |
| `src/components/dashboard/WeekLoad.tsx` | Deleted |

Full diff: `git show d8b797801672f2e03d3303f4283736480a00436e`

</details>
