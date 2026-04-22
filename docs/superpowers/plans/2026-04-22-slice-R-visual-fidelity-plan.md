# Slice R-visual — Visual-fidelity sweep plan

**Date:** 2026-04-22
**Spec:** ../specs/2026-04-22-slice-R-visual-fidelity.md
**Parent design:** ../../../design_handoff_bookrag_reader/README.md

Each task = one gap. Tests-first where testable. Every AC is gated by either a Vitest computed-style/DOM assertion or a Playwright `getComputedStyle` probe inside `frontend/e2e/slice-R-visual-fidelity.spec.ts`. One final Playwright flow test (T21) exercises all changes end-to-end.

---

## T1 — Extract reader top bar; remove global NavBar from reader; add right-side pill group

**Targets ACs:** AC-TopBar, AC-AskPill

**Writing-tests-first:**
1. Add Playwright test `'reader top bar has no library/upload nav'`:
   - Navigate to `/books/:id/read/1`.
   - Assert `[data-testid="reading-screen"] a[href="/upload"]` has count 0.
   - Assert `header[data-testid="reader-topbar"]` exists with height `52px`.
2. Add Playwright test `'Ask pill uses accent background'`:
   - Locate `button[aria-label="Ask"]` inside the top bar.
   - `getComputedStyle(el).backgroundColor` resolves to the computed `--accent` oklch (convert to RGB via a `getPropertyValue` probe comparison).
   - `border-radius` = `999px`; `color` = `var(--paper-00)` RGB.

**Implementation:**
1. Create `frontend/src/components/reader/ReaderTopBar.tsx`:
   - Props: `title: string`, `spreadLabel?: string`, `mode`, `onToggleMode`, `onAsk?`.
   - Root: `<header data-testid="reader-topbar">` styled per README §1 (52px, 14px/28px padding, 3-column CSS grid, bottom hairline).
   - Left: back button `← Library` (ported from current ReadingScreen inline back button).
   - Center: italic-serif title.
   - Right: flex row `gap: 8px` → `IconBtn` wrapping `IcSearch`, `IconBtn` wrapping `IcBookmark`, Ask pill button (`padding: 6px 14px`, `border-radius: 999px`, `background: var(--accent)`, `color: var(--paper-00)`, font-sans 12px weight 600), then `ReadingModeToggle`.
2. Remove `<NavBar />` from `ReadingScreen.tsx`; render `<ReaderTopBar />` instead. Delete the inline 52px grid in the screen.
3. Leave Search/Bookmark/Ask handlers as no-op callbacks for this slice (wiring is out of scope; the pill only needs to be visible and clickable for a11y snapshots).

## T2 — Verify book shadow reaches the DOM; fix any ancestor clipping

**Targets ACs:** AC-BookShadow

**Writing-tests-first:**
1. Playwright test: `getComputedStyle(book).boxShadow` contains the substrings `"70px -24px"` and `"10px 20px -8px"`.
2. Playwright test: walk `book.parentElement` until `document.body`; none should have `overflow: "hidden"` or `clip-path`.

**Implementation:**
1. In `BookSpread.tsx`, the book itself has `overflow: "hidden"` (for the spine gradient). Move the clipping onto an inner absolutely-positioned child that wraps only the two pages + spine gradient, leaving the outer `[data-testid="book-spread"]` with `overflow: visible`.
2. In `ReadingScreen.tsx`, confirm the stage grid and root have no `overflow: hidden`. They don't today; test guards against regression.

## T3 — S1 empty card: 3 suggested questions with mono bullets + `IcSpark`

**Targets ACs:** AC-S1List, AC-S1Icon

**Writing-tests-first:**
1. Vitest on `S1EmptyCard`: assert `queryAllByRole('listitem')` length 3; each has a leading `<span data-testid="bullet-N">` with computed `font-family` containing `"Plex Mono"`.
2. Vitest: `container.querySelector('[data-testid="s1-empty-card"] svg path')` has `getAttribute('d')` = the handoff IcSpark path.

**Implementation:**
1. Update `S1EmptyCard.tsx`:
   - Replace `✦` with `<IcSpark size={16} />`.
   - Below the heading, render an `<ol>` with 3 items using inline styles: grid `[auto 1fr]`, numeral span uses `var(--mono)` 11px `var(--ink-3)`, body uses `var(--serif)` 13.5px `var(--ink-1)`, `margin-bottom: 6px`.
   - Use these canned strings (flag in the PRD open question for design review):
     - "Who is this character?"
     - "What just happened here?"
     - "What does this phrase mean?"

## T4 — Replace `IcSpark`, `IcSend`, `IcHighlight` paths; add `IcChevron`

**Targets ACs:** AC-IcSpark, AC-IcSend, AC-IcChevron

**Writing-tests-first:**
1. Vitest on `icons.test.tsx` (new): render each icon, assert `path[d]` equals the exact handoff path strings. Include `IcChevron`.

**Implementation:**
1. Edit `frontend/src/components/icons.tsx`:
   - `IcSpark`: replace with multi-segment path from `icons.jsx` line 26.
   - `IcSend`: replace with `d="M13.5 2.5L2.5 7l5 1.5L9 13.5l4.5-11z"`; drop inline fill.
   - `IcHighlight`: replace with handoff line 32 path.
   - Add `export const IcChevron = (p: Props) => <Icon {...p} d="M4 6l4 4 4-4" />;`.

## T5 — Selection toolbar enter animation

**Targets ACs:** AC-SelectionToolbarMotion

**Writing-tests-first:**
1. Playwright test: trigger a selection, then inside `getComputedStyle(toolbar).animationDuration` equals `"180ms"` and `animationName` is a keyframe defined in the reader CSS.

**Implementation:**
1. Add to `frontend/src/styles/animations.css`:
   ```css
   @keyframes rr-toolbar-enter {
     from { opacity: 0; transform: translate(-50%, -100%) translateY(-2px); }
     to   { opacity: 1; transform: translate(-50%, -100%) translateY(-6px); }
   }
   .rr-toolbar-enter { animation: rr-toolbar-enter 180ms ease; }
   ```
2. Attach `className="rr-toolbar-enter"` to the SelectionToolbar root.

## T6 — Reading mode toggle — padding/radius/border

**Targets ACs:** AC-ReadingModeToggle

**Writing-tests-first:**
1. Vitest: render toggle, compute `getComputedStyle`: `padding` = `"5px 12px"`, `border-radius` = `"999px"`, `border-style` = `"none"` OR `border-width` = `"0px"`.

**Implementation:**
1. `ReadingModeToggle.tsx`: set `padding: "5px 12px"`, `borderRadius: 999`, remove border lines; tweak hover/active states (no border swap).

## T7 — Page turn arrow — circular, size 48, opacity 0.5, IcArrow icons

**Targets ACs:** AC-PageTurnArrow

**Writing-tests-first:**
1. Playwright test in reading-mode on state:
   - `width: "48px"`, `height: "48px"`, `border-radius: "999px"`, `opacity: "0.5"`.
   - `button svg path` has the IcArrowR `d`.

**Implementation:**
1. `PageTurnArrow.tsx`: set width 48, height 48, borderRadius 999, base opacity 0.5 (→ 1 on hover via inline `onMouseEnter`/`Leave` or a CSS class). Render `<IcArrowL size={18} />` / `<IcArrowR size={18} />` instead of text glyphs.

## T8 — Progress hairline — track = `--paper-2`

**Targets ACs:** AC-ProgressHairline

**Writing-tests-first:**
1. Playwright: track background `background-color` matches `getComputedStyle(document.documentElement).getPropertyValue("--paper-2")` once converted to `rgb`.

**Implementation:**
1. `ProgressHairline.tsx`: set track `background: "var(--paper-2)"`.

## T9 — Pacing label — uppercase, 12px, letter-spacing 1.4px, top position

**Targets ACs:** AC-PacingLabel

**Writing-tests-first:**
1. Playwright:
   - `font-size: "12px"`, `text-transform: "uppercase"`, `letter-spacing: "1.4px"`.
   - `getBoundingClientRect().top` < `80`.

**Implementation:**
1. `PacingLabel.tsx`: change size to 12, letterSpacing to `"1.4px"`, add `textTransform: "uppercase"`, color `var(--ink-3)`.
2. `ReadingScreen.tsx`: wrap the rendered `PacingLabel` in a fixed-position container at top center (top: 16, left: 50%, transform: translateX(-50%), z-index: 99).

## T10 — NotePeek — full redesign per spec (360px, orange border-left, paper-00, 10px radius, 20px 40px shadow, "ago" meta)

**Targets ACs:** AC-NotePeek

**Writing-tests-first:**
1. Playwright test after hovering a note in reading mode: width 360, border-left 3px oklch(58% 0.1 55), border-radius 10, background paper-00, box-shadow `"0 20px 40px -12px"` substring, padding `"12px 16px"`, inner text contains `"ago"`.

**Implementation:**
1. Pass `createdAt` through the peek state in ReadingScreen: update `PeekState` to include `body, x, y, createdAt`.
2. Update `NotePeekPopover.tsx`:
   - `width: 360`, `background: var(--paper-00)`, `border: 1px solid var(--paper-2)`, `borderLeft: "3px solid oklch(58% 0.1 55)"`, `borderRadius: 10`, `padding: "12px 16px"`, `boxShadow: "0 20px 40px -12px rgba(28,24,18,.2)"`.
   - Add `<div>` under body: relative-time string formatted from `createdAt` ("just now", "N min ago", "N hr ago", "N day(s) ago"). Small sans 10.5px `var(--ink-3)`.

## T11 — Reading mode legend font-size → 10.5

**Targets ACs:** AC-Legend

**Writing-tests-first:**
1. Vitest: `getComputedStyle(legend).fontSize` = `"10.5px"`.

**Implementation:**
1. `ReadingModeLegend.tsx`: `fontSize: 10.5`.

## T12 — Chat-open animation: card flip-in stagger + phrase pulse

**Targets ACs:** AC-ChatOpenAnim

**Writing-tests-first:**
1. Playwright: select text, click Ask; within 600ms, the anchored span's `animation-name` includes `rr-highlight-pulse`, and the new `[data-card-kind="ask"]`'s `animation-name` includes `rr-card-enter`.
2. Vitest on `AskCard`: a newly-mounted card (not flash) renders with `className` containing `rr-card-enter`.

**Implementation:**
1. Add to `frontend/src/styles/animations.css`:
   ```css
   @keyframes rr-card-enter {
     from { opacity: 0; transform: translateX(-12px) rotate(-0.2deg); }
     to   { opacity: 1; transform: translateX(0) rotate(-0.2deg); }
   }
   .rr-card-enter { animation: rr-card-enter 520ms cubic-bezier(.2,.7,.2,1) both; }

   @keyframes rr-highlight-pulse {
     0%   { background: var(--accent-soft); }
     100% { background: transparent; }
   }
   .rr-highlight-pulse { animation: rr-highlight-pulse 600ms ease-out; }
   ```
2. In `AskCard.tsx`: accept `enterDelay?: number` prop; add `className="rr-card-enter"` with inline `animationDelay` on initial mount (`useRef` gate so animation only plays once).
3. In `ReadingScreen.tsx` `onAction` ask branch: after `askAndStream` resolves, apply `rr-highlight-pulse` class to the anchor sentence element for 600ms. First card uses delay 60ms, subsequent 200ms — track an index via a ref.

## T13 — Skeleton card header-label text

**Targets ACs:** AC-Skeleton

**Writing-tests-first:**
1. Vitest: `<SkeletonAskCard />` renders text matching `/THINKING · gathering 3 more passages/`.

**Implementation:**
1. Update `SkeletonAskCard.tsx` to include a header strip: font-sans 9.5px, letter-spacing 1.3px, uppercase, `var(--accent-ink)`, weight 600. Text: `THINKING · gathering 3 more passages`.

## T14 — Drop cap in px (54px) + padding in px

**Targets ACs:** AC-DropCap

**Writing-tests-first:**
1. Playwright: evaluate `getComputedStyle(paragraph, "::first-letter").fontSize` = `"54px"`; `padding` string contains `"4px"` and `"8px"`; `float` = `"left"`.

**Implementation:**
1. `reader-typography.css`: rewrite `.rr-dropcap::first-letter` to `font-size: 54px; padding: 4px 8px 0 0; line-height: 0.9;` — remove `em` values.

## T15 — Stave tag computed-style test (cosmetic)

**Targets ACs:** AC-StaveTag

**Writing-tests-first:**
1. Playwright: first child `<div>` inside the left page is the stave tag; assert `font-size: "11.5px"`, `letter-spacing: "0.4px"`, `color` resolves to `--ink-3`.

**Implementation:**
1. `BookSpread.tsx`: change `letterSpacing: 0.4` to `letterSpacing: "0.4px"` to make it explicit (React coerces unitless numbers to px but explicit is easier to assert).

## T16 — Folio row: add author on the right

**Targets ACs:** AC-Folio

**Writing-tests-first:**
1. Playwright: spread's folio row has two children; first has mono font; second contains a non-empty string and uses italic serif.

**Implementation:**
1. Surface author: check `frontend/src/lib/api.ts` Chapter type. If `author` is missing on `Chapter`, add a `fetchBook(bookId)` and store `author` in ReadingScreen state; pass as prop to `BookSpread`. Fall back to empty string for loading state.
2. `BookSpread.tsx`: render `<span style={{ fontStyle: "italic", fontSize: 11, color: "var(--ink-3)" }}>{author}</span>` in the right slot.

## T17 — Keep token file in sync (safety check)

**Writing-tests-first:**
1. Vitest: assert `:root { --accent }` resolves to `oklch(62% 0.045 145)` exactly (guards against accidental drift).

**Implementation:**
1. No changes expected. Confirmed `frontend/src/styles/tokens.css` is a verbatim copy of `design_handoff_bookrag_reader/tokens.css` (lowercased hex only).

## T18 — Remove `.selection-toolbar` CSS block that conflicts with inline component

**Writing-tests-first:**
Covered by T5 animation assertion (the component's class takes over).

**Implementation:**
1. Delete or rename the unused `.selection-toolbar` / `.selection-toolbar-btn` / `.selection-toolbar-arrow` blocks in `frontend/src/styles/annotations.css` — they don't apply today (component uses inline style) but invite future regressions. Keep `.annot-peek` and other annotation helpers.

## T19 — Consolidated Playwright e2e spec

**Writing-tests-first:**
1. Create `frontend/e2e/slice-R-visual-fidelity.spec.ts`:
   - One `describe` per AC group: Top bar, Book, Cards, Reading mode, Motion, Typography.
   - Uses a single test fixture book + chapter with one pre-seeded ask card and one pre-seeded note to exercise NotePeek quickly.
2. Each spec invokes `getComputedStyle` via `page.evaluate`.

**Implementation:**
Covered as each AC is implemented — tests live in one file, updated as tasks land.

## T20 — Screenshot baselines

**Writing-tests-first / implementation (together):**
1. Add Playwright `toHaveScreenshot` calls at the end of each flow state:
   - `reader-default.png`
   - `reader-with-ask.png` (after card enter animation settles — wait `animationend`)
   - `reader-reading-mode-on.png`
   - `note-peek-open.png`
2. Commit baselines under `frontend/e2e/slice-R-visual-fidelity.spec.ts-snapshots/` after a clean local run.

## T21 — End-of-slice flow validation

**Targets ACs:** AC-FlowBaseline (covers every other AC in one pass)

1. Playwright test `full reader pass`:
   1. Navigate to library → click first book → lands on `/books/:id/read/1`.
   2. Assert reader top bar (AC 1–2).
   3. Assert book shadow + drop cap + stave tag + folio (AC 3, 18, 19, 20).
   4. Select text in the first paragraph → SelectionToolbar appears with correct animation (AC 9).
   5. Click Ask → S3 skeleton appears with "THINKING" label (AC 17), card enter animation fires, highlight pulse fires (AC 16).
   6. Select another phrase → click Note → note card renders with orange border.
   7. Click Reading-mode toggle → top bar dims, margin column slides out, pacing label appears at top (AC 13), arrows + hairline + legend render correctly (AC 11, 12, 15).
   8. Hover the noted phrase → NotePeek popover appears with 360px width, orange border, "ago" meta (AC 14).
   9. Toggle Reading mode off → margin column returns.
   10. Capture `reader-default` + `reader-reading-mode-on` + `reader-with-ask` + `note-peek-open` screenshots (AC 21).

## Task dependency order

```
T17 (sanity) ──┐
               ├─► T4 (icons) ──► T1 (top bar) ──► T7 (arrows) ──► T9 (pacing)
               │                                       │
T18 (cleanup)──┤                                       ├──► T21 (flow)
               │                                       │
T14 (dropcap) ─┼─► T15 (stave) ─► T16 (folio) ─► T2 (shadow)
               │
T3 (S1) ────── T13 (skeleton) ──► T12 (motion)
               │
T5 (toolbar) ─ T6 (toggle) ─ T8 (hairline) ─ T10 (peek) ─ T11 (legend)
```

Tasks T4/T17/T18 are safe to land first (pure refactors). Top-bar (T1) is the largest structural change and should land before T2/T7/T9 so the arrow + pacing placements have the right chrome context. T21 runs last to prove everything together.

## Review checkpoints

1. **After T1–T4**: design review of top bar, icons, and S1 card against the visualizer's "V3 Inline default" artboard.
2. **After T12**: design review of chat-open animation timing.
3. **After T21**: full flow playback + screenshot diff review before merge.
