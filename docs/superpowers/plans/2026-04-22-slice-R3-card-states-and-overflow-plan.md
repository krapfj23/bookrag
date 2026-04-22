# Slice R3 — Card states (S1–S7) + O2 overflow — Implementation Plan

**Date:** 2026-04-22
**Parent spec:** `docs/superpowers/specs/2026-04-22-slice-R3-card-states-and-overflow.md`
**Evaluator gate:** `frontend/e2e/slice-R3-card-states-and-overflow.spec.ts`

## Baseline facts confirmed from exploration

- `cards.ts` already defines `followups: { question; answer }[]` on `AskCard`. No schema migration needed; R3 adds runtime-only optional flags (`loading`, `streaming`, `followupLoading`) that MUST be stripped before `writeStoredCards`.
- `MarginColumn.tsx` currently does only `cards.filter((c) => visibleSids.has(c.anchor))` and renders each via `AskCard`/`NoteCard`. R3 layers the S2 connector, S6/S7 prefixes, and O2 partition on top of this filtered list.
- `askFlow.askAndStream` is the single entry point for "create → query → simulateStream". It needs a sibling `followupAndStream` that calls `appendFollowup` + streams into the last follow-up's `answer`, and a hook for the `loading`/`streaming` transient flags.
- `ReadingScreen.tsx` owns `spreadIdx` (page side context for S7) and `bookRef` (geometry source for S2 connector + S6 edge bar + jump CTA target).
- No backend, API, or contract change.
- `useCards.ts` commits via `writeStoredCards` after every `updateAsk`. To prevent `loading`/`streaming` flags leaking to localStorage, the persistence layer in `cards.ts` must strip them at write time — that is the safest structural fix.

Perspective applied throughout: **minimum-surface diff per task, tests-first, geometry and overflow logic isolated into pure helpers so Playwright can exercise them deterministically.**

---

## T1 — Extend card type with transient runtime flags + strip on persist

**Goal:** Add optional `loading`/`streaming`/`followupLoading` to `AskCard` and strip them inside `writeStoredCards` so transient state never round-trips.

**Files**
- Modify: `frontend/src/lib/reader/cards.ts`
- Test: `frontend/src/lib/reader/cards.test.ts` (new)

**Failing test (full code):** verify (a) a stored `AskCard` with `loading: true` is written back without the flag; (b) `readStoredCards` returns what was actually persisted; (c) `NoteCard` is untouched; (d) re-reading yields no `loading` key.

**Run:** `cd frontend && npm test -- --run src/lib/reader/cards.test.ts` → expected fail: `expected undefined, received true`.

**Implementation:** extend `AskCard` interface with three optional transient flags; update `writeStoredCards` to `JSON.parse(JSON.stringify(...))` then delete `loading|streaming|followupLoading` on each `kind === "ask"` card before persisting.

**Run:** `cd frontend && npm test -- --run src/lib/reader/cards.test.ts` → PASS.

**Commit**
```
git add frontend/src/lib/reader/cards.ts frontend/src/lib/reader/cards.test.ts
git commit -m "Slice R3 T1: add transient card flags and strip on persist"
```

---

## T2 — `useCards.appendFollowup` + `setAskLoading` + `setAskStreaming`

**Goal:** Add the three new mutators to `useCards` so `askFlow` can drive S3 skeleton/cursor + S5 follow-up threads.

**Files**
- Modify: `frontend/src/lib/reader/useCards.ts`
- Test: `frontend/src/lib/reader/useCards.test.tsx`

**Failing test:** renderHook, create an ask card; call `appendFollowup(id, "q", "")` then mutate the latest followup's answer via `updateAsk`; assert `cards[0].followups.length === 1` and `.answer === "streamed"`. Second test: `setAskLoading(id, true)` flips `card.loading` in state but after a manual `writeStoredCards` cycle the persisted copy has no `loading` key (integration with T1).

**Run:** fail on `appendFollowup is not a function`.

**Implementation:** add `appendFollowup(id, question, initialAnswer = "")` that `updateAsk`s to push `{ question, answer: initialAnswer }`. Add `setAskLoading(id, loading)` and `setAskStreaming(id, streaming)` that update transient flags in in-memory state (use `updateAsk`; persistence strip in T1 handles the write-path). Export `appendFollowup`, `setAskLoading`, `setAskStreaming` from the hook return.

**Run:** PASS.

**Commit**
```
git add frontend/src/lib/reader/useCards.ts frontend/src/lib/reader/useCards.test.tsx
git commit -m "Slice R3 T2: add appendFollowup and transient flag setters to useCards"
```

---

## T3 — `askFlow` drives `loading` → `streaming` lifecycle + new `followupAndStream`

**Goal:** Wire the S3 state machine: set `loading=true` on create, flip to `loading=false, streaming=true` on first chunk, `streaming=false` when stream ends. Add `followupAndStream`.

**Files**
- Modify: `frontend/src/lib/reader/askFlow.ts`
- Test: `frontend/src/lib/reader/askFlow.test.ts`

**Failing test:** stub `queryBook` that resolves after 30ms; stub `updateAsk` capturing call sequence; assert sequence starts with `loading:true`, then first onChunk triggers `{loading:false, streaming:true}`, final state `streaming:false`. Second test for `followupAndStream` asserting followup appended pre-stream and its `answer` grows.

**Run:** fail: `followupAndStream is not defined`.

**Implementation:** inject `setAskLoading`/`setAskStreaming` into `AskFlowInput`; call `setAskLoading(id,true)` right after `createAsk`, then in the `onChunk` wrapper detect the first chunk (previous `soFar === ""`) and call `setAskLoading(id,false); setAskStreaming(id,true)`; after `simulateStream` resolves call `setAskStreaming(id,false)`. Add `followupAndStream` that calls `appendFollowup(id, question, "")`, sets `followupLoading=true`, runs `simulateStream`, updates only the last followup's answer via `updateAsk`, clears the flag.

**Run:** PASS.

**Commit**
```
git add frontend/src/lib/reader/askFlow.ts frontend/src/lib/reader/askFlow.test.ts
git commit -m "Slice R3 T3: drive loading/streaming lifecycle and add followupAndStream"
```

---

## T4 — `SkeletonAskCard` + `BlinkingCursor` components (S3)

**Goal:** Present the two S3 visual states.

**Files**
- Create: `frontend/src/components/reader/SkeletonAskCard.tsx`
- Create: `frontend/src/components/reader/BlinkingCursor.tsx`
- Modify: `frontend/src/styles.css` (or `frontend/src/styles/animations.css`) to add `@keyframes blink { 0%,100% {opacity:1} 50% {opacity:0} }`.
- Test: `frontend/src/components/reader/SkeletonAskCard.test.tsx`

**Failing test:** render `<SkeletonAskCard />`; assert `data-testid="skeleton-ask-card"` visible, text `THINKING · gathering 3 more passages`, two shimmer divs present. Render `<BlinkingCursor />`; assert `data-testid="blinking-cursor"`, inline style contains `animation: blink 1s infinite` and `width:6px`, `height:14px`.

**Run:** fail — components not exported.

**Implementation:** build both as presentational components. Skeleton uses `var(--paper-00)` background, 9.5px uppercase header, two animated placeholder lines (simple `opacity` shimmer via inline `@keyframes shimmer`). BlinkingCursor renders an inline-block span using `var(--ink-2)` with the required animation.

**Run:** PASS.

**Commit**
```
git add frontend/src/components/reader/SkeletonAskCard.tsx frontend/src/components/reader/BlinkingCursor.tsx frontend/src/components/reader/SkeletonAskCard.test.tsx frontend/src/styles/animations.css
git commit -m "Slice R3 T4: add SkeletonAskCard and BlinkingCursor components"
```

---

## T5 — `AskCard` renders S3 skeleton/cursor and S4 scroll region + fade

**Goal:** Wire `card.loading` to render the Skeleton instead of the card body; while `card.streaming` append `<BlinkingCursor />` after `card.answer`. If rendered answer height > 220px, constrain with `maxHeight:220, overflow:auto` and overlay a gradient fade at the bottom.

**Files**
- Modify: `frontend/src/components/reader/AskCard.tsx`
- Test: `frontend/src/components/reader/AskCard.test.tsx` (new)

**Failing test:** render AskCard with `loading:true` → skeleton testid visible, ask-answer not visible. With `streaming:true, answer:"hi"` → cursor testid visible next to text. With long answer (mock `offsetHeight` via ref) → container has `overflow:auto` and fade overlay `data-testid="ask-answer-fade"` exists.

**Run:** fail.

**Implementation:** in AskCard, early-return `<SkeletonAskCard />` if `card.loading`. Use a ref + `ResizeObserver` (or `useLayoutEffect` measuring `scrollHeight`) to flip `isLong` state when content ≥ 220px. Wrap answer in a `<div>` with conditional `maxHeight:220, overflowY:"auto"` and render a sibling positioned-absolute fade div. Append `<BlinkingCursor />` if `card.streaming`.

**Run:** PASS.

**Commit**
```
git add frontend/src/components/reader/AskCard.tsx frontend/src/components/reader/AskCard.test.tsx
git commit -m "Slice R3 T5: AskCard renders S3 skeleton/cursor and S4 scroll/fade"
```

---

## T6 — `FollowupComposer` + thread rendering inside `AskCard` (S5)

**Goal:** Pinned single-line composer below answer; submitting appends to `card.followups` via `followupAndStream`; rendered followups indented 14px with dashed left border and `FOLLOW-UP` header.

**Files**
- Create: `frontend/src/components/reader/FollowupComposer.tsx`
- Modify: `frontend/src/components/reader/AskCard.tsx`
- Test: `frontend/src/components/reader/FollowupComposer.test.tsx`

**Failing test:** render composer with `onSubmit` spy; type "why?", press Enter; spy called with `"why?"` and input cleared. Render AskCard with two seeded followups → two `[data-testid="followup"]` blocks with dashed border-left-style "dashed", `FOLLOW-UP` header visible.

**Run:** fail.

**Implementation:** composer = controlled `<input placeholder="Ask a follow-up…">` with `onKeyDown` Enter handler. AskCard: new prop `onFollowup?: (q: string) => void`, new prop `composerRef?: React.Ref<HTMLInputElement>` (used by S5 duplicate-focus behavior). Render the composer below the fade container. Map `card.followups` into threaded blocks; if `card.followupLoading` and it's the last followup, append `<BlinkingCursor />`.

**Run:** PASS.

**Commit**
```
git add frontend/src/components/reader/FollowupComposer.tsx frontend/src/components/reader/AskCard.tsx frontend/src/components/reader/FollowupComposer.test.tsx
git commit -m "Slice R3 T6: follow-up composer and threaded followups in AskCard"
```

---

## T7 — Anchor geometry helpers + `useAnchorVisibility` hook (S6)

**Goal:** Pure helper `getAnchorRect(bookRoot, sid)` + hook `useAnchorVisibility(sids, bookRoot)` returning `Map<sid, { visible: boolean; direction: "up"|"down"|null; top: number }>` using `IntersectionObserver`.

**Files**
- Create: `frontend/src/lib/reader/anchorGeometry.ts`
- Create: `frontend/src/lib/reader/useAnchorVisibility.ts`
- Test: `frontend/src/lib/reader/anchorGeometry.test.ts`
- Test: `frontend/src/lib/reader/useAnchorVisibility.test.tsx`

**Failing test:** JSDOM-mock an `IntersectionObserver`; render two `<span data-sid>` elements, simulate one entry with `isIntersecting:false, boundingClientRect.top < 0`; assert map reports `direction:"up"`. `getAnchorRect` test: creates DOM, asserts returns correct `DOMRect` proxy or `null` if sid missing.

**Run:** fail.

**Implementation:** `getAnchorRect(root, sid)` = `root.querySelector([data-sid="${sid}"])?.getBoundingClientRect() ?? null`. Hook attaches IO to each sid's element, updates state on entries; direction derived from `entry.boundingClientRect.top` sign relative to `root`.

**Run:** PASS.

**Commit**
```
git add frontend/src/lib/reader/anchorGeometry.ts frontend/src/lib/reader/useAnchorVisibility.ts frontend/src/lib/reader/anchorGeometry.test.ts frontend/src/lib/reader/useAnchorVisibility.test.tsx
git commit -m "Slice R3 T7: anchor geometry helpers and visibility hook"
```

---

## T8 — `AnchorEdgeBar` + `JumpToAnchorCTA` + S6 prefix in AskCard/NoteCard

**Goal:** When an anchor is detected off-screen, AskCard/NoteCard headers prefix with `↑ SCROLL UP · ` or `↓ SCROLL DOWN · `. Render a 3px vertical edge bar component and a "Jump to anchor on this page" CTA button.

**Files**
- Create: `frontend/src/components/reader/AnchorEdgeBar.tsx`
- Create: `frontend/src/components/reader/JumpToAnchorCTA.tsx`
- Modify: `frontend/src/components/reader/AskCard.tsx`
- Modify: `frontend/src/components/reader/NoteCard.tsx`
- Test: `frontend/src/components/reader/AnchorEdgeBar.test.tsx`

**Failing test:** edge bar receives `{top:120, color:"var(--accent)"}` → renders absolutely positioned div at `top:120` with `width:3`, `background` matching. CTA click fires `onJump`. AskCard with prop `offscreen:{direction:"up"}` → header text starts with `↑ SCROLL UP ·`.

**Run:** fail.

**Implementation:** both presentational. AskCard/NoteCard gain optional `offscreen?: {direction:"up"|"down"}` and `onJump?: ()=>void` props. If `offscreen`, header prefix added and `<JumpToAnchorCTA onClick={onJump}>` rendered below the card body.

**Run:** PASS.

**Commit**
```
git add frontend/src/components/reader/AnchorEdgeBar.tsx frontend/src/components/reader/JumpToAnchorCTA.tsx frontend/src/components/reader/AskCard.tsx frontend/src/components/reader/NoteCard.tsx frontend/src/components/reader/AnchorEdgeBar.test.tsx
git commit -m "Slice R3 T8: off-screen anchor prefix, edge bar, and jump CTA"
```

---

## T9 — Page-side detection + S7 cross-page prefix

**Goal:** Given the current spread's left/right `sid` sets, determine whether a card's anchor is on the opposite page of its "natural side" and render `← FROM p. {n} · ` / `→ FROM p. {n} · ` prefix.

**Files**
- Create: `frontend/src/lib/reader/pageSide.ts`
- Modify: `frontend/src/components/reader/AskCard.tsx`
- Modify: `frontend/src/components/reader/NoteCard.tsx`
- Test: `frontend/src/lib/reader/pageSide.test.ts`

Semantics: the margin column sits on the right of the spread, so anchors on the left page are "cross-page" from the card. Apply `← FROM p. {leftFolio} ·` when anchor `sid` is in left-page sids; `→ FROM p. {rightFolio} ·` reserved for future left-margin. For R3 we emit `← FROM p. {n} ·` only when anchor is on the left page.

**Failing test:** `computeCrossPage({sid:"p1.s2", leftSids, rightSids, leftFolio:1, rightFolio:2})` returns `{direction:"left", folio:1}`. AskCard renders header prefix containing `← FROM p. 1 ·`.

**Run:** fail.

**Implementation:** `pageSide.ts` exports `computeCrossPage`. AskCard/NoteCard accept optional `crossPage?: {direction:"left"|"right"; folio:number}` prop and prepend the appropriate arrow + folio string in the header. If both `offscreen` and `crossPage` present, spec examples show S7 prefix wins (crossPage renders first, offscreen prefix suppressed since the anchor isn't on the same page).

**Run:** PASS.

**Commit**
```
git add frontend/src/lib/reader/pageSide.ts frontend/src/components/reader/AskCard.tsx frontend/src/components/reader/NoteCard.tsx frontend/src/lib/reader/pageSide.test.ts
git commit -m "Slice R3 T9: compute cross-page anchor and render S7 prefix"
```

---

## T10 — `AnchorConnector` SVG + S2 single-card rule

**Goal:** Render dashed SVG connector from the card's left edge to the anchor's bounding rect **only when exactly one expanded card is visible**. Reposition on window resize + spread change.

**Files**
- Create: `frontend/src/components/reader/AnchorConnector.tsx`
- Test: `frontend/src/components/reader/AnchorConnector.test.tsx`

**Failing test:** render with `{from:{x:100,y:50}, to:{x:300,y:80}}`; assert svg `path` `d` begins with `M 100 50` and ends `300 80`; `stroke-dasharray` nonzero; `stroke-opacity` ~`0.6`; color = `var(--accent)`.

**Run:** fail.

**Implementation:** pure SVG component rendering an absolutely positioned svg layer (pointer-events:none) sized to `window.innerWidth/Height`; draws a quadratic Bezier or straight path with dashed stroke. Parent (MarginColumn, T11) owns the resize listener and geometry computation.

**Run:** PASS.

**Commit**
```
git add frontend/src/components/reader/AnchorConnector.tsx frontend/src/components/reader/AnchorConnector.test.tsx
git commit -m "Slice R3 T10: AnchorConnector SVG component"
```

---

## T11 — O2 overflow partition helpers + `CollapsedCardRow` + `LatestExpandedDivider`

**Goal:** Pure `partitionForOverflow(cards)` returning `{ collapsed, expanded }` with latest 2 (by `updatedAt`) expanded and rest collapsed; divider shown only if `collapsed.length > 0`. Two new presentational components.

**Files**
- Create: `frontend/src/lib/reader/overflow.ts`
- Create: `frontend/src/components/reader/CollapsedCardRow.tsx`
- Create: `frontend/src/components/reader/LatestExpandedDivider.tsx`
- Test: `frontend/src/lib/reader/overflow.test.ts`
- Test: `frontend/src/components/reader/CollapsedCardRow.test.tsx`

**Failing test:** `partitionForOverflow` with 4 cards of varying `updatedAt` → two oldest in `collapsed`, two newest in `expanded`. 2 cards → all expanded, `collapsed:[]`. Row test: `data-testid="collapsed-card-row"`, text `p.{n} · {italic question} · ›`, `border-left:3px solid var(--accent)` for ask.

**Run:** fail.

**Implementation:** `partitionForOverflow` + `getFolioFromAnchor(sid)` helper (`p{n}` → `n`). Row is a button that calls `onExpand(card.id)`. Divider renders 9.5px uppercase `Latest · expanded` between flanking 1px `var(--paper-2)` rules.

**Run:** PASS.

**Commit**
```
git add frontend/src/lib/reader/overflow.ts frontend/src/components/reader/CollapsedCardRow.tsx frontend/src/components/reader/LatestExpandedDivider.tsx frontend/src/lib/reader/overflow.test.ts frontend/src/components/reader/CollapsedCardRow.test.tsx
git commit -m "Slice R3 T11: overflow partition plus collapsed row and divider"
```

---

## T12 — `MarginColumn` integrates S2/S6/S7 + O2 partition + expand-on-click

**Goal:** Rewire MarginColumn to (a) partition via `partitionForOverflow`, (b) render collapsed rows + divider + expanded tail, (c) compute `crossPage` and `offscreen` per card and pass to AskCard/NoteCard, (d) render `AnchorConnector` when exactly 1 expanded card, (e) maintain a local `manuallyExpandedIds` set so clicking a collapsed row promotes it (dropping the now-oldest expanded).

**Files**
- Modify: `frontend/src/components/reader/MarginColumn.tsx`
- Modify: `frontend/src/components/reader/MarginColumn.test.tsx`

**Failing test:** render MarginColumn with 3 ask cards → 1 collapsed row + divider + 2 expanded. Click collapsed row → previously oldest-expanded becomes collapsed, clicked card becomes expanded. With 1 expanded card, assert `AnchorConnector` testid present; with 2+ expanded, absent.

**Run:** fail.

**Implementation:** new props `leftSids, rightSids, leftFolio, rightFolio, bookRoot, onJump(sid), onFollowup(cardId, question)`. Internal `useAnchorVisibility` over visible sids; internal state for manually-expanded overrides the `updatedAt` latest-2 rule. Wraps rendering in a `<div style="position:relative">` so `AnchorConnector` can be absolutely positioned.

**Run:** PASS.

**Commit**
```
git add frontend/src/components/reader/MarginColumn.tsx frontend/src/components/reader/MarginColumn.test.tsx
git commit -m "Slice R3 T12: MarginColumn renders O2 overflow, S2 connector, S6/S7 prefixes"
```

---

## T13 — `ReadingScreen` wires new MarginColumn props + duplicate-ask focuses composer

**Goal:** Supply `leftSids/rightSids/leftFolio/rightFolio/bookRoot/onJump/onFollowup` to MarginColumn. Change duplicate-ask handler to focus the existing card AND focus its follow-up composer (S5 supersedes R2 focus-only).

**Files**
- Modify: `frontend/src/screens/ReadingScreen.tsx`

Test coverage: deferred to the E2E (T14) — ReadingScreen is integration glue and the behavior is verified end-to-end.

**Implementation:** compute `leftSids`/`rightSids` from `current.left`/`current.right`; `leftFolio = spreadIdx*2+1`; `rightFolio = spreadIdx*2+2`; `bookRoot = bookRef.current`. `onJump(sid)` queries the matching `[data-sid]` in book root and calls `scrollIntoView({block:"center"})` + a brief CSS flash class. `onFollowup(cardId, q)` calls `followupAndStream({bookId, maxChapter:cursor-chapter, cardId, question:q, appendFollowup, updateAsk, queryBook})`. Duplicate-ask branch: instead of only `flash(existing.id)`, also sets `focusedComposerCardId` state passed to MarginColumn which focuses the matching composer via `ref`.

**Commit**
```
git add frontend/src/screens/ReadingScreen.tsx
git commit -m "Slice R3 T13: wire MarginColumn props and duplicate-ask composer focus"
```

---

## T14 — Playwright evaluator gate `slice-R3-card-states-and-overflow.spec.ts`

**Goal:** Single E2E spec mapping 1:1 to PRD AC 1–10.

**Files**
- Create: `frontend/e2e/slice-R3-card-states-and-overflow.spec.ts`

**Tests (each maps to a single AC):**
1. `S1 invitation shown with zero cards` — clear localStorage, expect `s1-empty-card` testid.
2. `S2 connector SVG present with one card` — seed 1 ask via selection+Ask, expect single `data-testid="anchor-connector"` svg; seed a second card and expect it absent.
3. `S3 skeleton then blinking cursor during ask` — mock `/query` with `await route.fulfill` after 400ms delay; after clicking Ask, expect `skeleton-ask-card` visible, then `blinking-cursor` visible while answer grows, then cursor gone once final text present.
4. `S4 scrollable + fade on long answer` — mock `/query` returning a 2000-char answer; expect `ask-answer` container `overflow: auto` via `evaluate(el => getComputedStyle(el).overflowY)` and `ask-answer-fade` testid visible.
5. `S5 follow-up composer appends threaded reply` — after initial ask, fill `ask-a-follow-up` input with "why?", press Enter; expect `[data-testid="followup"]` with text containing "synthesized answer".
6. `S5b duplicate-ask focuses composer` — after seeding an ask, select same sid again, click Ask → expect follow-up composer focused (evaluate `document.activeElement`).
7. `S6 off-screen prefix + edge bar + jump CTA` — seed a card, then `page.evaluate(() => window.scrollTo(0, 4000))` to push the anchor out of view; expect card header contains `↑ SCROLL UP ·`, `anchor-edge-bar` visible, `jump-to-anchor-cta` visible; click CTA → anchor back in view.
8. `S7 cross-page prefix` — author two spreads via chapter mock with enough sentences; seed a card on page 1, turn to next spread; expect `← FROM p. 1 ·` prefix on the card if still in `visibleSids`.
9. `O2 collapse with 3+ cards + divider + expand-on-click` — pre-seed 3 ask cards in localStorage before navigate; expect 1 `collapsed-card-row` + `latest-expanded-divider` + 2 expanded; click row → previously-oldest-expanded becomes collapsed.

Uses the R2 spec's mock scaffolding as a template. Adds a `chapterSize:"large"` variant to generate enough paragraphs to trigger multi-spread pagination for the S7 test.

**Run:** `cd frontend && npx playwright test slice-R3-card-states-and-overflow.spec.ts` → all PASS.

**Commit**
```
git add frontend/e2e/slice-R3-card-states-and-overflow.spec.ts
git commit -m "Slice R3 T14: evaluator gate spec for S1-S7 and O2"
```

---

## Dependencies and sequencing

- T1 → T2 (cards.ts types underpin the hook).
- T2 → T3 (askFlow consumes the new setters).
- T4 independent; T5 needs T4 (imports components).
- T6 needs T3 (followupAndStream exists) and T5 (AskCard layout).
- T7 → T8 (edge bar consumes geometry hook).
- T9 independent of T7/T8.
- T10 independent; consumed by T12.
- T11 → T12.
- T12 consumes T8, T9, T10, T11.
- T13 consumes T12 (new MarginColumn API).
- T14 last; verifies the whole slice.

## Potential challenges

- **IntersectionObserver in JSDOM:** T7 unit test must mock `IntersectionObserver` globally.
- **Playwright scroll for S6:** The reading screen's stage is centered with `placeItems:center` — the window may not actually scroll. Mitigation: have the S6 test reduce viewport height via `page.setViewportSize({width:1280, height:400})` so the anchor genuinely falls out of view.
- **Pagination for S7 test:** the R2 mock's 3-sentence chapter fits one spread. The T14 S7 test needs a dedicated mock returning enough paragraphs to create 2+ spreads.
- **Connector geometry timing:** AnchorConnector depends on layout post-mount; must recompute in `requestAnimationFrame` after `resize`/`spreadIdx`/`cards` changes. An initial compute on first paint is required or the svg's path endpoints will be stale on first render.
- **Transient flag leakage:** T1's strip-on-write pattern must be applied at every `writeStoredCards` call site — no path should ever bypass it.

---

## Summary

14 tasks. 14 frontend source files created, 8 modified, 0 deleted, 0 backend files touched. Evaluator gate: `frontend/e2e/slice-R3-card-states-and-overflow.spec.ts`. Test-first every task; pure helpers (`anchorGeometry`, `pageSide`, `overflow`, `askFlow` lifecycle) isolated from rendering for deterministic unit + Playwright coverage.
