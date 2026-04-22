# Slice R-visual — Visual-fidelity sweep PRD

**Date:** 2026-04-22
**Parent:** ../../../design_handoff_bookrag_reader/README.md

## Goal
Close the gap between the shipped reader (post-R4) and the design handoff so every surface reads as a pixel-for-pixel realization of the "linen paper + sage accent" spec — correct chrome, correct card/peek/pill dimensions, correct motion, and the missing S1/chat-open/pulse affordances.

## Gap list

Each gap: (a) handoff section violated, (b) current state, (c) expected state, (d) files to change.

1. **Reading-surface top bar is the wrong bar**
   (a) README §1 top bar
   (b) `ReadingScreen.tsx` renders the generic `<NavBar>` *plus* a secondary 52px row (back / title / spread-count + toggle). The global NavBar adds an unwanted product-nav row at the top of the reading surface.
   (c) A single 52px three-column grid: `← Library` | italic-serif title | right-side pill group `[IcSearch] [IcBookmark] [Ask]`. The Ask pill uses `background: var(--accent)` with white text (`var(--paper-00)`). No global NavBar on the reader.
   (d) `frontend/src/screens/ReadingScreen.tsx`.

2. **Top-bar right side missing Search + Bookmark + Ask pill**
   (a) README §1
   (b) Only a spread-count `"1 / N"` label and `ReadingModeToggle` are rendered.
   (c) Add three right-aligned controls: `IcSearch` icon button, `IcBookmark` icon button, and an `Ask` pill (var(--accent) bg, white text, radius 999px). `ReadingModeToggle` stays as the trailing item.
   (d) `frontend/src/screens/ReadingScreen.tsx`, possibly new `frontend/src/components/reader/ReaderTopBar.tsx`.

3. **Book shadow is too flat in render**
   (a) README §1 book spread shadow
   (b) Values in `BookSpread.tsx` match the spec string, but the screenshot (`flow-03-ask-card.png`) shows nearly no ambient shadow. Likely because the stage container supplies `placeItems: "center"` and the shadow layers land on the same paper tint. Verify spec shadow is reaching the DOM without being clipped by `overflow: hidden`.
   (c) Computed `box-shadow` on `[data-testid="book-spread"]` equals literally `0 30px 70px -24px rgba(28,24,18,.2), 0 10px 20px -8px rgba(28,24,18,.08)` and is visible above the paper background (no ancestor `overflow: hidden` clips it — move the `overflow: hidden` off the book and onto a child mask if needed).
   (d) `frontend/src/components/reader/BookSpread.tsx`, `frontend/src/screens/ReadingScreen.tsx` (stage container).

4. **S1 empty card missing 3 suggested questions with mono-numeral bullets**
   (a) README §2 S1
   (b) `S1EmptyCard.tsx` renders sparkle badge + serif heading + one generic sans subtitle (`Select a phrase to Ask, Note, or Highlight.`).
   (c) Add three list items below the heading, each bullet using `font-family: var(--mono)` numeral (`1.` `2.` `3.`), serif body text, 13.5px, `var(--ink-1)`. Use sample questions from the visualizer's S1 artboard.
   (d) `frontend/src/components/reader/S1EmptyCard.tsx`.

5. **Sparkle icon in S1 uses a text glyph, not `IcSpark`**
   (a) README §2 S1, Assets list
   (b) S1 renders the literal character `✦` at 16px.
   (c) Render `<IcSpark size={16} />` inside the 34×34 accent-softer badge.
   (d) `frontend/src/components/reader/S1EmptyCard.tsx`.

6. **`IcSpark` path diverges from handoff**
   (a) README Assets — "port icons from `icons.jsx`"
   (b) Current `IcSpark` has 8 segments (cardinal + diagonal lines with different lengths) — drawn from a different iteration.
   (c) Match `icons.jsx` line 26: `d="M8 2v3M8 11v3M2 8h3M11 8h3M4 4l2 2M10 10l2 2M12 4l-2 2M4 12l2-2"`.
   (d) `frontend/src/components/icons.tsx`.

7. **`IcChevron` is missing**
   (a) README Assets
   (b) No export for `IcChevron` in `icons.tsx`.
   (c) Export `IcChevron = d="M4 6l4 4 4-4"`.
   (d) `frontend/src/components/icons.tsx`.

8. **`IcSend` / `IcHighlight` paths diverge from handoff**
   (a) README Assets
   (b) `IcSend` current path is a longer piecewise polygon with `fill="currentColor"`. Handoff `IcSend` is `d="M13.5 2.5L2.5 7l5 1.5L9 13.5l4.5-11z"`. `IcHighlight` differs similarly.
   (c) Replace both with the handoff paths.
   (d) `frontend/src/components/icons.tsx`.

9. **Selection toolbar text-only — spec doesn't require icons but the animation duration is wrong**
   (a) README §5 motion ("fade + 4px slide up, 180ms")
   (b) `SelectionToolbar` inline transition is `opacity 180ms ease, transform 180ms ease` but the element has no enter animation; `annotations.css .selection-toolbar` uses `annot-fadeUp 140ms` with a 6px translate.
   (c) Add an `annot-fadeUp` style keyframe that goes from `translateY(4px)` to `0` over 180ms ease and attach it to the `SelectionToolbar` root.
   (d) `frontend/src/components/SelectionToolbar.tsx`, `frontend/src/styles/annotations.css`.

10. **`ReadingModeToggle` padding/radius/border diverge from spec**
    (a) README §4 toggle pill
    (b) `padding: 4px 12px`, `borderRadius: 20`, `border: 1.5px solid ...`.
    (c) `padding: 5px 12px`, `border-radius: 999px` (use `var(--r-pill)`), no border (spec doesn't specify one; off-state is flat on `var(--paper-1)`).
    (d) `frontend/src/components/reader/ReadingModeToggle.tsx`.

11. **`PageTurnArrow` is square + solid, wrong size, wrong content**
    (a) README §4
    (b) 40×40, `borderRadius: 8`, renders literal `←`/`→` text glyphs, `opacity: 1`.
    (c) 48×48, `border-radius: 999px` (circular), `opacity: 0.5` (rising to 1 on hover), render `<IcArrowL />` / `<IcArrowR />` at `size={18}`.
    (d) `frontend/src/components/reader/PageTurnArrow.tsx`.

12. **`ProgressHairline` uses `var(--ink-4)` instead of `var(--paper-2)`**
    (a) README §4
    (b) Track background is `var(--ink-4)`.
    (c) Track `background: var(--paper-2)`; foreground stays `var(--accent)`.
    (d) `frontend/src/components/reader/ProgressHairline.tsx`.

13. **`PacingLabel` not uppercase, wrong size/letter-spacing, wrong position, wrong total-label casing**
    (a) README §4
    (b) 13px, normal case, `letter-spacing: 0.02em`, rendered with `ordinal(total)` (e.g. "Stave One · of Five"), and — per screenshot — positioned at bottom-left, not the top.
    (c) 12px, `text-transform: uppercase`, `letter-spacing: 1.4px`, italic serif, `var(--ink-3)`. Fade in at **top** center. Example: `STAVE ONE · OF FIVE` (both ordinals uppercase is fine; the spec writes "of five" lowercase but after uppercase transform they match).
    (d) `frontend/src/components/reader/PacingLabel.tsx`, `frontend/src/screens/ReadingScreen.tsx`.

14. **`NotePeekPopover` styling diverges heavily**
    (a) README §4 note peek
    (b) `background: var(--paper-0)`, `border: 1px solid var(--ink-3)`, `borderRadius: 8`, `padding: 8px 12px`, `maxWidth: 280`, `boxShadow: 0 4px 16px rgba(0,0,0,0.12)`, no orange left border, no timestamp row.
    (c) `background: var(--paper-00)`, `border-left: 3px solid oklch(58% 0.1 55)` (plus a 1px top/right/bottom hairline), `border-radius: 10px`, `padding: 12px 16px`, `width: 360px`, `box-shadow: 0 20px 40px -12px rgba(28,24,18,.2)`. Add a small "2 days ago" style meta line under the body (placeholder relative-time; use `createdAt` from the note card).
    (d) `frontend/src/components/reader/NotePeekPopover.tsx`, `frontend/src/screens/ReadingScreen.tsx` (pass timestamp through the peek state).

15. **`ReadingModeLegend` — font-size is 10px, spec is 10.5px**
    (a) README §4
    (b) `fontSize: 10`.
    (c) `fontSize: 10.5`.
    (d) `frontend/src/components/reader/ReadingModeLegend.tsx`.

16. **Chat-open animation absent (card flip-in stagger + highlight pulse)**
    (a) README §6 (AN3) + §5 step 3
    (b) Ask cards simply appear; `.rr-card-flash` glows the card once but does not animate a flip-in, and the anchored phrase on the page does not pulse.
    (c) Add:
      - `@keyframes rr-card-enter` — initial `opacity: 0; transform: translateX(-12px) perspective(600px) rotateY(-8deg);` → final `opacity: 1; transform: rotate(-0.2deg);` over 520ms smooth ease. Apply once on mount to newly-created `AskCard`.
      - `@keyframes rr-highlight-pulse` — background flash on the anchored `[data-sid]` span for ~600ms when its card is created (first card 60ms delay, subsequent cards 200ms stagger).
    (d) `frontend/src/styles/animations.css`, `frontend/src/components/reader/AskCard.tsx`, `frontend/src/screens/ReadingScreen.tsx` (trigger pulse on newly created ask id).

17. **Skeleton "thinking" card missing the spec's header-label text**
    (a) README §2 S3
    (b) `SkeletonAskCard` probably renders generic shimmer (confirmed by test file). Spec requires a header strip reading `THINKING · gathering 3 more passages`.
    (c) Update skeleton to include the labeled header strip (sans 9.5px, letter-spacing 1.3px, uppercase, `var(--accent-ink)`).
    (d) `frontend/src/components/reader/SkeletonAskCard.tsx`.

18. **Body font-size on reading page is 15px but drop cap is declared in `em`, not `px`**
    (a) README §1 drop cap "54px serif"
    (b) `.rr-dropcap::first-letter { font-size: 3.8em; }` → at 15px parent that's 57px. Padding uses `em`, not `4px 8px 0 0`.
    (c) `font-size: 54px; padding: 4px 8px 0 0;` float left (matches spec literally). Keep `::first-letter` to preserve sid anchoring.
    (d) `frontend/src/styles/reader-typography.css`.

19. **Chapter stave-tag label reads "Chapter N · of M" not "Stave …"**
    (a) README §1 stave tag
    (b) `BookSpread.tsx` PageSide renders `Chapter ${num} · of ${totalChapters}` in `var(--ink-3)` italic serif 11.5px.
    (c) The stave label format is fine as "Chapter N · of M" (README calls it a "chapter stave tag"), but confirm computed values: italic serif, 11.5px, `letter-spacing: 0.4px`, `var(--ink-3)`. Current sets `letterSpacing: 0.4` (unitless — interpreted as 0.4px by React, OK). Leave as-is but add explicit `"0.4px"` unit for clarity.
    (d) `frontend/src/components/reader/BookSpread.tsx` — cosmetic only, assert in test.

20. **Folio row only renders a page number; spec calls out "page number + author" italic serif 11px**
    (a) README §1 folio
    (b) Only `{folio}` in mono font; no author on the opposite side of the row (there's a flex container with `justifyContent: space-between` but the second slot is empty).
    (c) Left slot: `{folio}` in mono. Right slot: `{book.author}` italic serif 11px `var(--ink-3)`. Pull author through `Chapter.author` or book meta — wire through ReadingScreen.
    (d) `frontend/src/components/reader/BookSpread.tsx`, `frontend/src/screens/ReadingScreen.tsx`, `frontend/src/lib/api.ts` (if author not already on chapter response).

## Acceptance criteria

Each AC is verifiable via `getComputedStyle` / DOM assertion in Playwright (`frontend/e2e/slice-R-visual-fidelity.spec.ts`) or Vitest computed-style tests, OR via a `toHaveScreenshot` baseline for holistic looks.

1. **AC-TopBar**: No `<header>` descendant of `[data-testid="reading-screen"]` contains the text "Library · Reading · Upload" nav. A single 52px row contains `← Library`, an italic-serif title, and a right-side group including an accessible `button[aria-label="Ask"]` whose computed `background-color` equals `var(--accent)` resolved. (Playwright computed-style check.)
2. **AC-AskPill**: The Ask button has `border-radius: 999px` (computed), color resolves to `var(--paper-00)`, and sits to the left of the Reading-mode toggle. (Playwright.)
3. **AC-BookShadow**: `getComputedStyle([data-testid="book-spread"]).boxShadow` string contains `70px -24px` and `10px 20px -8px`; no ancestor in the path from `body` → book element has `overflow: hidden`. (Playwright `evaluate`.)
4. **AC-S1List**: When rendered with zero cards, `[data-testid="s1-empty-card"]` contains exactly 3 list items (`role=listitem` or `li`), each with a `::marker`-like mono-numeral prefix (computed `font-family` of numeral span contains "Plex Mono"). (Vitest.)
5. **AC-S1Icon**: `[data-testid="s1-empty-card"] svg` exists with path `d="M8 2v3M8 11v3..."`. (Vitest snapshot of the SVG.)
6. **AC-IcSpark**: `IcSpark` renders a `<path>` whose `d` attribute equals `"M8 2v3M8 11v3M2 8h3M11 8h3M4 4l2 2M10 10l2 2M12 4l-2 2M4 12l2-2"`. (Vitest.)
7. **AC-IcChevron**: `IcChevron` is importable from `@/components/icons` and renders `<path d="M4 6l4 4 4-4" />`. (Vitest.)
8. **AC-IcSend**: `IcSend`'s path `d` equals `"M13.5 2.5L2.5 7l5 1.5L9 13.5l4.5-11z"`. (Vitest.)
9. **AC-SelectionToolbarMotion**: The selection toolbar's computed `animation-duration` is `180ms` and it translates 4px on enter. (Playwright computed-style + snapshot comparison of initial-frame screenshot.)
10. **AC-ReadingModeToggle**: Computed padding is `5px 12px`; `border-radius` is `999px`; `border-width` is `0px` (or border shorthand is `none`). (Playwright.)
11. **AC-PageTurnArrow**: `[data-testid="page-arrow-right"]` computed `width` = `48px`, `height` = `48px`, `border-radius` = `999px`, `opacity` = `0.5`. Contains an `<svg>` whose first path `d` equals the `IcArrowR` path. (Playwright.)
12. **AC-ProgressHairline**: Track background computes to the `--paper-2` hex (`rgb(227, 222, 211)` in light). (Playwright.)
13. **AC-PacingLabel**: Computed `font-size` = `12px`, `text-transform` = `uppercase`, `letter-spacing` = `1.4px`, positioned within top 80px of viewport (not bottom). (Playwright.)
14. **AC-NotePeek**: Computed `width` = `360px`, `border-left-width` = `3px`, `border-left-color` resolves to `oklch(58% 0.1 55)`, `border-radius` = `10px`, `padding` = `12px 16px`, `background-color` = `--paper-00`, and a meta line containing "ago" is present. (Playwright.)
15. **AC-Legend**: Computed `font-size` = `10.5px`. (Playwright.)
16. **AC-ChatOpenAnim**: Triggering Ask fires `rr-card-enter` animation on the new `AskCard` (detected by watching `animationstart` via `addEventListener`), and the anchored `[data-sid]` span receives the `rr-highlight-pulse` animation within 260ms of Ask trigger. Total first-card duration ~520ms. (Playwright `evaluate`.)
17. **AC-Skeleton**: While `card.loading`, the skeleton's header strip text equals `THINKING · gathering 3 more passages`. (Vitest.)
18. **AC-DropCap**: `.rr-dropcap::first-letter` computed `font-size` = `54px`, `float` = `left`, `padding` = `4px 8px 0px 0px`. (Playwright via `getComputedStyle(el, '::first-letter')`.)
19. **AC-StaveTag**: Chapter stave tag computed `font-size` = `11.5px`, `letter-spacing` = `0.4px`, `color` resolves to `--ink-3`. (Playwright.)
20. **AC-Folio**: Folio row contains both a mono-font number and an italic-serif author string; layout computed justification is `space-between`. (Playwright.)
21. **AC-FlowBaseline**: End-to-end flow pass (`T_N`) — open a book, select text, Ask (→ card flips in, phrase pulses), Note, toggle Reading mode (legend + hairline + arrows correct), hover a note (peek popover correct), toggle off. One Playwright `toHaveScreenshot` per surface state: `reader-default`, `reader-with-ask`, `reader-reading-mode-on`, `note-peek-open`. (Baselines committed.)

## UI scope

- `frontend/src/screens/ReadingScreen.tsx`
- `frontend/src/components/reader/BookSpread.tsx`
- `frontend/src/components/reader/S1EmptyCard.tsx`
- `frontend/src/components/reader/SkeletonAskCard.tsx`
- `frontend/src/components/reader/AskCard.tsx`
- `frontend/src/components/reader/ReadingModeToggle.tsx`
- `frontend/src/components/reader/PageTurnArrow.tsx`
- `frontend/src/components/reader/ProgressHairline.tsx`
- `frontend/src/components/reader/PacingLabel.tsx`
- `frontend/src/components/reader/NotePeekPopover.tsx`
- `frontend/src/components/reader/ReadingModeLegend.tsx`
- `frontend/src/components/SelectionToolbar.tsx`
- `frontend/src/components/icons.tsx`
- `frontend/src/styles/reader-typography.css`
- `frontend/src/styles/animations.css`
- `frontend/src/styles/annotations.css`
- New: `frontend/src/components/reader/ReaderTopBar.tsx`
- New: `frontend/e2e/slice-R-visual-fidelity.spec.ts`

## Backend scope

**None.** Confirmed. Only `Chapter.author` may need surfacing (gap #20) — the backend response already contains book metadata; if it doesn't include author at the chapter endpoint, route it via an existing books endpoint on the frontend. No new endpoints, no pipeline changes.

## Out of scope

- Card detail (edit/delete) view — README §2 explicitly calls this out as "design pass needed first."
- Virtual pagination improvements (README "Known gaps").
- Mobile/touch adaptations.
- Dark-mode specific visual tuning beyond what tokens already give us for free.
- Card-to-span SVG connector production upgrades (`AnchorConnector` stays as-is; only the card's enter animation changes).

## Open questions

- **Author source for folio**: Does `GET /books/{id}/chapters/{n}` return author, or must the screen fetch book metadata separately? (Verify via `frontend/src/lib/api.ts` — if absent, add a lightweight `fetchBook(bookId)` call cached per screen mount.)
- **S1 suggested questions — canned vs dynamic?** Spec says "3 suggested questions" without specifying source. Assume canned strings sourced from the visualizer artboard (e.g., "Who is Scrooge's nephew?", "What is Marley's chain?", "Where does the Ghost first appear?"). Confirm with design before merge.
- **Chat-open pulse color**: The spec says "background flash" but not the color value. Assume `var(--accent-soft)` fading to transparent. Confirm in review.
