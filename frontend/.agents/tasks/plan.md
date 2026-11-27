# Implementation Plan — Three-color professional background + dashboard declutter

All paths are relative to `c:\Users\razor\OneDrive\Documents\GitHub\opencampus\frontend`.
Do NOT touch `../backend/`. No new dependencies. Keep token NAMES; change values only (one new token pair is added for the warm region).

## Design decisions (fixed — do not re-decide)

**Three hue families and their regions:**

1. **Slate-navy (cool base)** — canvas, topbar, all standard cards (`oc-panel` / `--oc-surface`): AssignmentList, TodaySchedule, search field, mobile tab bar. The "everyday" family.
2. **Muted sage-teal (identity/structure)** — sidebar rail, WelcomeSection hero, AcademicProgress panel (`--oc-lavender` repointed to sage). These are the structural/identity regions, so the sage hue reads as a deliberate left-to-top band, not a sprinkle.
3. **Warm sand/greige (counterweight)** — CampusEventCard (existing `--oc-apricot`, re-tuned) and a new warm panel behind CampusUpdates (`--oc-apricot-soft`, new token). The warm family owns the lower-right "campus life" corner.

Rationale: hue-to-region (not hue-to-component) mapping is what makes three colors read as composition instead of noise. Sage = structure, slate = content, warm = life.

**Kept:** `--oc-accent` #4f7bff for interactive elements (search focus, active states, Clear button). Subject tones, success/danger/pending unchanged except `--oc-subject-teal` (retuned so it doesn't sink into the new sage panels). Auth pages get the same token changes automatically plus one hardcoded-gradient fix in `.oc-blueprint-wash`; no auth layout restructuring.

---

## New token values (src/styles/index.css, `:root`)

All contrast ratios below were computed (WCAG relative luminance); every body-text pair on its actual background is ≥ 4.5:1.

### Sage-teal family (sidebar, hero, progress panel)
```
--oc-sidebar:      #182623   (deep sage; ink #e8edf7 on it ≈ 13.5:1)
--oc-lavender:     #1c2b27   (AcademicProgress panel; ink-subtle ≈ 4.6:1, ink-muted ≈ 6.4:1)
--oc-hero:         #1f3a34   (white text ≈ 12.2:1)
--oc-hero-light:   #2a4f45   (white text ≈ 9.1:1, gradient end)
```
The hero's `.oc-hero` grid lines and `ArchMotif` stay white — they work on sage exactly as on navy.

### Slate-navy family (canvas, cards)
```
--oc-canvas:            #10151f
--oc-surface:           #1b2230
--oc-surface-sunken:    #131826
--oc-periwinkle:        #26304a   (soft navy tint: search-mark bg, avatar bg, BrandMark stroke)
--oc-line:              #212a3e
--oc-line-strong:      #2d3a55
```

### Warm family (event card, updates strip)
```
--oc-apricot:       #2b241c   (event card bg — slightly warmer/sandier than before)
--oc-apricot-ink:   #f0c9a6   (warm foreground text; on #2b241c ≈ 9.5:1)
--oc-apricot-soft:  #242019   (NEW — CampusUpdates panel bg; ink-muted ≈ 5.9:1, ink ≈ 12.5:1)
```
Also add `--color-apricot-soft: var(--oc-apricot-soft);` to the `@theme` block (one new Tailwind utility `bg-apricot-soft`).

### Ink scale (bumped for the new surfaces)
```
--oc-ink:          #e8edf7   (unchanged)
--oc-ink-muted:    #93a7c4   (≥ 5.9:1 on every family background)
--oc-ink-subtle:   #7d92b8   (5.0:1 on surface, 4.6:1 on sage panel — use ink-muted for body copy on sage)
```

### Subject tone retune
```
--oc-subject-teal:  #3ecfc4   (bluer/brighter mint so subject marks don't vanish on #1c2b27)
```
All other subject tones, success/danger/pending, accent, signal: unchanged.

### Body background (calm, max two radials)
```css
background-image:
  radial-gradient(80rem 55rem at 20% -15%, rgb(42 79 69 / 0.28), transparent 65%),   /* sage glow, top-left over the sidebar/hero band */
  radial-gradient(45rem 35rem at 95% 85%, rgb(70 56 38 / 0.10), transparent 60%);   /* faint warm glow, bottom-right over the campus corner */
```

### Shadows — tighten (less spread, softer)
```
--oc-shadow-1: 0 1px 2px rgb(0 0 0 / 0.25), 0 3px 10px -4px rgb(0 0 0 / 0.35);
--oc-shadow-2: 0 2px 4px rgb(0 0 0 / 0.28), 0 8px 20px -10px rgb(0 0 0 / 0.45);
--oc-shadow-3: 0 4px 8px rgb(0 0 0 / 0.3), 0 16px 36px -14px rgb(0 0 0 / 0.55);
```

### `.oc-blueprint-wash` (auth aside) — retune hardcoded hexes to sage
Replace the hardcoded gradient stops `#10192b / #141d33 / #1a2540` with `#16211e / #1a2823 / #1e2f29`, and change the grid-line color from `rgb(79 123 255 / 0.06|0.04)` to `rgb(255 255 255 / 0.05|0.035)` so the auth panel matches the sage sidebar. `background-color: var(--oc-sidebar)` already picks up the new sage value.

---

## Per-file edit list

### A. Color system

- [ ] 1. **Update all token values + body background + shadows + add `--oc-apricot-soft` and its `@theme` mapping.**
      File: `src/styles/index.css` — apply every value above; also retune `.oc-blueprint-wash` as above. Do not rename or delete any existing token.
      Verify: `npm run build` in the frontend dir passes (tsc + vite build), and the compiled `dist/index.html`/CSS contains `#1f3a34`, `#182623`, `#2b241c` (spot-check via `Select-String` in `dist/assets/*.css`).

### B. Decluttering

- [ ] 2. **Delete `src/components/dashboard/AiAssistantTeaser.tsx` and `src/components/dashboard/QuickActions.tsx`; remove their imports and grid slots from `src/pages/Dashboard.tsx`.** Replace both with one slim, quiet row at the bottom of the grid (a plain `<p className="oc-eyebrow">` line, no card, no icons): "Notes, quizzes, study planning and an AI assistant are coming soon." — rendered only when `!searching`. Remove the now-unused `lg:order-1/2` reshuffle: WelcomeSection becomes `lg:order-1 lg:col-span-12` (full width, since the teaser's 4-column slot is gone), and renumber remaining orders.
      Files: delete `src/components/dashboard/AiAssistantTeaser.tsx`, `src/components/dashboard/QuickActions.tsx`; edit `src/pages/Dashboard.tsx`.
      Verify: `npm run build` passes; `grep -r "AiAssistantTeaser\|QuickActions" src` returns nothing.

- [ ] 3. **Sidebar (`src/components/Sidebar.tsx`): reduce the 7 "Coming soon" items to 3** — keep `Academics`, `Assignments`, `Planner`; delete `Resources`, `AI Assistant`, `Campus Life`, `Notes` from the `UPCOMING` array and drop their now-unused icon imports. Keep the single "Coming soon" eyebrow as the one label (no per-item badges — there are none today; do not add any).
      Verify: `npm run build` passes; the rendered list (dev server or built HTML) shows 3 items.

- [ ] 4. **WelcomeSection (`src/components/dashboard/WelcomeSection.tsx`): remove the "Sample data" pill; drop the tasks-done progress bar; simplify the up-next card.**
      - Delete the `Sample data` span (keep the institution name line, lose the `justify-between` wrapper if it becomes empty on the right).
      - Remove the "X of Y tasks done" progress link block (AssignmentList already shows "n of m done" — duplicated message).
      - In the up-next card, remove the "Up next / Happening now" eyebrow label row (the big time + subject + room already say it); keep one line each: time (large), subject, `kind · room`. Keep the `DayRail` (it is already minimal) but render it full-width where the progress bar was.
      - Remove the `ArrowRight` icon from the card (the whole card is the link; the chevron is decoration). Drop unused imports (`ArrowRight`).
      - Drop the `tasksDone`/`tasksTotal` props and update `Dashboard.tsx`'s call site (remove the props and the `tasksDone` computation there).
      Files: `src/components/dashboard/WelcomeSection.tsx`, `src/pages/Dashboard.tsx`.
      Verify: `npm run build` passes.

- [ ] 5. **AssignmentList (`src/components/dashboard/AssignmentList.tsx`): remove the WeekLoad strip and the Priority pill.**
      - Delete the `WeekLoad` import and its bordered wrapper `div` (the `!searching` block at the top of the panel).
      - Delete the `src/components/dashboard/WeekLoad.tsx` file.
      - Remove the `Priority` pill span (both branches — also the `sr-only` "high priority" text can go; keep `a.priority` in the data model untouched). Keep the subject code + SubjectMark line.
      - Keep COLLAPSED_COUNT = 3, the checkbox toggle, "Show all" button, and due-date coloring.
      Files: `src/components/dashboard/AssignmentList.tsx`; delete `src/components/dashboard/WeekLoad.tsx`.
      Verify: `npm run build` passes; `grep -r "WeekLoad" src` returns nothing.

- [ ] 6. **AcademicProgress (`src/components/dashboard/AcademicProgress.tsx`): delete the featured "Up next" card entirely** (the `showFeatured` block with the disabled Continue button). Remove the `featured` prop from the interface and drop the `featured` computation + prop pass in `Dashboard.tsx`. The panel becomes just the per-subject list on the sage block (`.bg-lavender` now sage via tokens — no class change needed).
      Files: `src/components/dashboard/AcademicProgress.tsx`, `src/pages/Dashboard.tsx`. Drop the unused `ArrowRight` import.
      Verify: `npm run build` passes.

- [ ] 7. **CampusUpdates (`src/components/dashboard/CampusUpdates.tsx`): warm panel + quieter rows.**
      - Wrap the list in `rounded-card bg-apricot-soft p-4 sm:p-5` (the warm counterweight region; date + category + title stay).
      - Replace the "Important" dot-and-label with a bare `size-1.5 rounded-full bg-subject-violet` dot (keep `title="Important"` or `sr-only` text for a11y), no word.
      - Keep date, category, title; keep category coloring.
      Files: `src/components/dashboard/CampusUpdates.tsx`.
      Verify: `npm run build` passes.

- [ ] 8. **TopBar (`src/components/TopBar.tsx`): remove the disabled theme (Palette) button** — a permanently disabled button is clutter (same principle as the Continue button). Also simplify the search-match banner in `Dashboard.tsx`: drop the re-quoted query text (the user just typed it in the field); keep "N matches" + Clear button only, e.g. `<p><span className="font-semibold">{filtered.total}</span> {matches} · press Esc or Clear</p>` — final wording up to the implementer, but NO re-display of the query string.
      Files: `src/components/TopBar.tsx` (remove Palette import + button), `src/pages/Dashboard.tsx`.
      Verify: `npm run build` passes.

- [ ] 9. **Passive border/shadow reduction sweep.** In one pass: `Sidebar.tsx` — keep the `border-r` (needed separation) but drop the `/60` opacity modifier complexity is fine as-is; `AssignmentList` — the `border-b` under the (now removed) WeekLoad is already gone; `WelcomeSection` — the up-next card's `border-l border-line` divider goes with the card simplification; `TodaySchedule` — leave structure intact (it is dense but informative; only remove the `Featured` "Now/Next" pill? NO — that is the now-indicator, keep it). Concretely: this item is the final visual sweep — remove any `border` utility whose element no longer needs separation after items 2-8, and downgrade `shadow-e2` to `shadow-e1` on non-interactive blocks (hero keeps `oc-hero`'s own shadow).
      Files: `src/components/dashboard/WelcomeSection.tsx`, `src/pages/Dashboard.tsx`, others as encountered.
      Verify: `npm run build` passes.

- [ ] 10. **Full build + visual check.**
      - `npm run build` — must be green.
      - Start dev server: `npm run dev` (background, port 5173) — verify the page renders (fetch `http://localhost:5173` returns 200 and the HTML references the app bundle); confirm in `dist/assets/*.css` that the three hue families are present: sage `#182623`/`#1f3a34`, slate `#1b2230`, warm `#2b241c`/`#242019`.
      - Confirm no removed component is imported: `Select-String -Path src -Pattern "AiAssistantTeaser|QuickActions|WeekLoad" -Recurse` returns nothing.
      - State in the final summary what was (and wasn't) visually verified — if no browser screenshot tool is available, say the check was build + compiled-CSS only.

## Things NOT to do (guards)

- Do not remove: search functionality, the assignment checkbox toggle, the schedule "now" indicator (red line + Now pill), any `aria-*`/`role` attributes, the responsive 12-column grid behavior, `NoMatches` empty states, `MobileTabBar`, `SystemStatus` (dev-only), the `Highlight` search-match markup.
- Do not rename or delete any `--oc-*` token (components reference them by name via `@theme`).
- Do not add dependencies; do not touch `../backend/`.
- Auth pages: token values flow in automatically via `:root`; only the `.oc-blueprint-wash` hardcoded hex retune (item 1) touches auth visuals. No layout changes there.

## Order rationale

Item 1 (tokens) first — every later visual edit renders against the final palette. Items 2-8 are independent component edits (each leaves the build green); do 2 before 4/6 since Dashboard's prop plumbing changes once there. Items 9-10 last.
