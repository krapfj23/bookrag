# Slice R1b — Reader fit-and-finish — Implementation Plan

**Date:** 2026-04-22
**Parent spec:** `docs/superpowers/specs/2026-04-22-slice-R1b-fit-and-finish.md`
**Evaluator gate:** `frontend/e2e/slice-R1b-fit-and-finish.spec.ts`

## T1 — Fixed-dimension `BookSpread`

**Goal:** `BookSpread` renders with a fixed outer width and min-height regardless of content length.

**Files**
- Modify: `frontend/src/components/reader/BookSpread.tsx`
- Modify (or add): `frontend/src/components/reader/BookSpread.test.tsx`

**Failing test (append):**
```tsx
it("has stable outer width and min-height across content sizes", () => {
  const thin = { left: [{ paragraph_idx: 0, sentences: [{ sid: "p1.s1", text: "A." }] }], right: [] };
  const fat = {
    left: Array.from({ length: 6 }, (_, i) => ({
      paragraph_idx: i,
      sentences: [{ sid: `p${i+1}.s1`, text: "Long paragraph ".repeat(12) }],
    })),
    right: Array.from({ length: 6 }, (_, i) => ({
      paragraph_idx: i+6,
      sentences: [{ sid: `p${i+7}.s1`, text: "Long paragraph ".repeat(12) }],
    })),
  };
  const { container, rerender } = render(
    <BookSpread chapter={{ num: 1, title: "Chapter 1", total_chapters: 3 }} spread={thin} cursor="p1.s1" />,
  );
  const thinBox = container.querySelector(".rr-book") as HTMLElement;
  const thinStyle = thinBox.getAttribute("style") || "";
  expect(thinStyle).toMatch(/width:\s*\d+px/);
  expect(thinStyle).toMatch(/min-height:\s*\d+px/);

  rerender(<BookSpread chapter={{ num: 1, title: "Chapter 1", total_chapters: 3 }} spread={fat} cursor="p1.s1" />);
  const fatBox = container.querySelector(".rr-book") as HTMLElement;
  expect(fatBox.getAttribute("style")).toContain(thinStyle.match(/width:\s*\d+px/)![0]);
});
```

**Implementation:** Add an explicit `style={{ width: 920, minHeight: 780, ...existing }}` (or the closest match to handoff figures) on the `.rr-book` element. Preserve existing styles via spread. Confirm via the test.

**Commit**
```
git add frontend/src/components/reader/BookSpread.tsx frontend/src/components/reader/BookSpread.test.tsx
git commit -m "Slice R1b T1: fixed BookSpread outer width and min-height"
```

---

## T2 — Revert `visibleSids` to current-spread-only

**Goal:** `MarginColumn` only sees the sids on the current spread. Cards whose anchor is outside this set don't render.

**Files**
- Modify: `frontend/src/screens/ReadingScreen.tsx`
- Modify: `frontend/src/screens/ReadingScreen.test.tsx` (add assertion)

**Failing test:** seed 3 cards on different spreads; navigate to spread 1; assert only cards anchored to sids on the current spread's left+right render (zero cross-spread cards).

**Implementation:** Replace the accumulated `visibleSids` union with `new Set([...currentSpread.left.flatMap(p => p.sentences).map(s => s.sid), ...currentSpread.right.flatMap(p => p.sentences).map(s => s.sid)])`. Remove the `sidToFolio` map used for cross-spread cards; cross-page prefix is now a purely intra-spread concept (left page vs right page).

**Commit**
```
git add frontend/src/screens/ReadingScreen.tsx frontend/src/screens/ReadingScreen.test.tsx
git commit -m "Slice R1b T2: visibleSids scoped to current spread only"
```

---

## T3 — `MarginColumn` S7 prefix uses intra-spread left/right pages only

**Goal:** `← FROM p. {leftFolio} ·` renders when a card's anchor is in the current spread's *left* page sids, while the margin is conceptually tied to the right page.

**Files**
- Modify: `frontend/src/components/reader/MarginColumn.tsx`
- Modify: `frontend/src/components/reader/MarginColumn.test.tsx`

**Failing test:** render MarginColumn with `leftSids=Set(["p1.s1"])`, `rightSids=Set(["p2.s1","p2.s2"])`, `leftFolio=1`, `rightFolio=2`, cards = one ask anchored to `p1.s1` + one ask anchored to `p2.s1`. Assert left-anchored card renders with header containing `← FROM p. 1 ·`; right-anchored card has no cross-page prefix.

**Implementation:** Simplify `computeCrossPage` call: drop the cross-spread fallback path added in R3. Only emit cross-page when `sid ∈ leftSids`.

**Commit**
```
git add frontend/src/components/reader/MarginColumn.tsx frontend/src/components/reader/MarginColumn.test.tsx
git commit -m "Slice R1b T3: S7 cross-page prefix limited to intra-spread left page"
```

---

## T4 — Chapter auto-advance on ArrowRight past last spread

**Goal:** ArrowRight on the last spread of chapter N (N < total_chapters) navigates to chapter N+1 spread 0. ArrowLeft on spread 0 of chapter N (N > 1) navigates to chapter N-1 last spread.

**Files**
- Modify: `frontend/src/screens/ReadingScreen.tsx`
- Modify: `frontend/src/screens/ReadingScreen.test.tsx`

**Failing test:** mock fetchChapter to return `total_chapters: 3`; render ReadingScreen at ch.1 with 1 spread; press ArrowRight; assert `useNavigate` called with `/books/:bookId/read/2`. Press ArrowLeft at ch.2 spread 0; expect navigate to `/books/:bookId/read/1` AND (when the new chapter renders) the ReadingScreen mounts with `spreadIdx` equal to that chapter's last spread.

**Implementation:**
1. Import `useNavigate` from `react-router-dom` in `ReadingScreen`.
2. In `turnForward`: when `spreadIdx >= spreads.length - 1`, check `body.chapter.num < body.chapter.total_chapters`; if so, `navigate(\`/books/${bookId}/read/${num + 1}\`)`. Otherwise no-op.
3. In `turnBackward`: when `spreadIdx <= 0`, if `body.chapter.num > 1`, navigate to `N - 1` and set a flag in navigation state `{ landOnLastSpread: true }` via `navigate(path, { state: { landOnLastSpread: true } })`.
4. On mount, check `location.state?.landOnLastSpread`; if true, after `body.kind === "ok"` initialize `spreadIdx` to `spreads.length - 1`.

**Commit**
```
git add frontend/src/screens/ReadingScreen.tsx frontend/src/screens/ReadingScreen.test.tsx
git commit -m "Slice R1b T4: arrow-key chapter advance on spread boundaries"
```

---

## T5 — Playwright gate `slice-R1b-fit-and-finish.spec.ts`

**Goal:** E2E coverage for all 4 ACs + regression check that R1/R2/R3 behaviors still hold (no new failures).

**Files**
- Create: `frontend/e2e/slice-R1b-fit-and-finish.spec.ts`

**Tests:**
1. `fixed spread dimensions across page turns` — mock a 2-spread chapter, read `bookSpread.boundingBox()` at spread 0, press ArrowRight, read again; expect identical width and equal-or-greater-than-baseline height.
2. `only current-spread cards render` — seed 2 ask cards with anchors on different spreads via localStorage; navigate; at spread 0, only the spread-0 card is visible; ArrowRight; now only the spread-1 card.
3. `arrow-right advances to next chapter at end` — mock 3-chapter book with 1 spread per chapter; navigate to ch.1; ArrowRight → URL is `/books/:bookId/read/2`. ArrowRight again → `/read/3`. ArrowRight on ch.3 last spread → URL unchanged.
4. `arrow-left returns to previous chapter last spread` — navigate to `/read/2`; ArrowLeft → URL is `/read/1` and spread counter shows `N/N` (last spread). ArrowLeft on `/read/1` spread 0 → no nav.
5. `R3 S7 cross-page prefix still fires intra-spread` — seed a card on p1.s1 on a 2-page spread where p2 is right; card renders with `← FROM p. 1 ·` prefix.

**Commit**
```
git add frontend/e2e/slice-R1b-fit-and-finish.spec.ts
git commit -m "Slice R1b T5: e2e gate for fit-and-finish"
```

---

## T6 — Regression sweep

**Goal:** Confirm R1/R2/R3 specs still pass after T1–T5.

**Commands**
```
source .venv/bin/activate && python -m pytest tests/ -v --tb=short
cd frontend && npm test -- --run
cd frontend && npx playwright test slice-R1 slice-R2 slice-R3 slice-R1b
```

No commit if clean. Fix any regressions and commit under `Slice R1b T6: <what>`.

## Summary

6 tasks. Frontend-only. Modifies `BookSpread.tsx`, `ReadingScreen.tsx`, `MarginColumn.tsx` (+ their tests). New Playwright spec `frontend/e2e/slice-R1b-fit-and-finish.spec.ts`.
