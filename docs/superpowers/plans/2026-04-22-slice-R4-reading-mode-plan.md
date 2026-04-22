# Slice R4 — Ambitious reading mode — Implementation Plan

**Date:** 2026-04-22
**Parent spec:** `docs/superpowers/specs/2026-04-22-slice-R4-reading-mode.md`
**Evaluator gate:** `frontend/e2e/slice-R4-reading-mode.spec.ts`

## Context summary

R4 is frontend-only, layered on R1–R3. No backend, no card schema changes. `fetchChapter` exposes `chapter.num` + `chapter.total_chapters` (pacing). Paginator state (`spreadIdx`, `body.spreads`, per-spread `left`/`right` with global `paragraph_idx`) + `chapter.paragraphs_anchored.length` gives the progress hairline.

## Architecture decisions

- **`useReadingMode(bookId)`** — key `bookrag.reading-mode.{bookId}`, default `"off"`, ignores malformed JSON, re-reads on `bookId` change.
- **`data-reading-mode="on"|"off"`** on reader root.
- **CSS transitions only** — 260ms margin slide-out, 420ms ambient gradient + widen.
- **Hover delegation** for note-peek — one `mouseover`/`mouseout` listener on `bookRef`, 150ms debounce, immediate hide; unmount removes.
- **MarginColumn `hidden` prop** — sets `aria-hidden="true"`, `opacity:0`, `translateX(40px)`, `pointer-events:none`, `transition: opacity 260ms ease, transform 260ms ease`. Stays in DOM.
- **Pacing** — `Stave ${ORDINALS[num-1] ?? num} · of ${ORDINALS[total-1] ?? total}`.
- **Progress** — `clamp((lastParaIdxOnSpread + 1) / totalParagraphs, 0, 1)` using the last right-page paragraph's global `paragraph_idx` (falls back to left if right empty).

---

## T1 — `useReadingMode(bookId)` hook

**Files**
- Create: `frontend/src/lib/reader/useReadingMode.ts`
- Test: `frontend/src/lib/reader/useReadingMode.test.tsx`

**Failing test**
```ts
import { describe, it, expect, beforeEach } from "vitest";
import { act, renderHook } from "@testing-library/react";
import { useReadingMode } from "./useReadingMode";

describe("useReadingMode", () => {
  beforeEach(() => localStorage.clear());

  it("defaults to off when no key present", () => {
    const { result } = renderHook(() => useReadingMode("book-a"));
    expect(result.current.mode).toBe("off");
  });

  it("reads persisted value for the bookId", () => {
    localStorage.setItem("bookrag.reading-mode.book-a", JSON.stringify("on"));
    const { result } = renderHook(() => useReadingMode("book-a"));
    expect(result.current.mode).toBe("on");
  });

  it("toggle flips and persists under per-book key", () => {
    const { result } = renderHook(() => useReadingMode("book-a"));
    act(() => result.current.toggle());
    expect(result.current.mode).toBe("on");
    expect(localStorage.getItem("bookrag.reading-mode.book-a")).toBe('"on"');
    act(() => result.current.toggle());
    expect(result.current.mode).toBe("off");
    expect(localStorage.getItem("bookrag.reading-mode.book-a")).toBe('"off"');
  });

  it("two books are isolated", () => {
    const a = renderHook(() => useReadingMode("book-a"));
    const b = renderHook(() => useReadingMode("book-b"));
    act(() => a.result.current.toggle());
    expect(a.result.current.mode).toBe("on");
    expect(b.result.current.mode).toBe("off");
  });

  it("ignores malformed JSON and defaults to off", () => {
    localStorage.setItem("bookrag.reading-mode.book-a", "not-json");
    const { result } = renderHook(() => useReadingMode("book-a"));
    expect(result.current.mode).toBe("off");
  });
});
```

**Run** `cd frontend && npm test -- --run useReadingMode` → fails.

**Implementation**
```ts
import { useCallback, useEffect, useState } from "react";

export type ReadingMode = "on" | "off";

function storageKey(bookId: string): string {
  return `bookrag.reading-mode.${bookId}`;
}

function read(bookId: string): ReadingMode {
  try {
    const raw = localStorage.getItem(storageKey(bookId));
    if (raw == null) return "off";
    const parsed = JSON.parse(raw);
    return parsed === "on" ? "on" : "off";
  } catch {
    return "off";
  }
}

export function useReadingMode(bookId: string) {
  const [mode, setModeState] = useState<ReadingMode>(() => read(bookId));

  useEffect(() => {
    setModeState(read(bookId));
  }, [bookId]);

  const setMode = useCallback(
    (next: ReadingMode) => {
      setModeState(next);
      try {
        localStorage.setItem(storageKey(bookId), JSON.stringify(next));
      } catch {}
    },
    [bookId],
  );

  const toggle = useCallback(() => {
    setMode(mode === "on" ? "off" : "on");
  }, [mode, setMode]);

  return { mode, toggle, setMode };
}
```

**Run** → PASS.

**Commit**
```
git add frontend/src/lib/reader/useReadingMode.ts frontend/src/lib/reader/useReadingMode.test.tsx
git commit -m "Slice R4 T1: useReadingMode hook with per-book localStorage"
```

---

## T2 — `ReadingModeToggle` pill

**Files**
- Create: `frontend/src/components/reader/ReadingModeToggle.tsx`
- Test: `frontend/src/components/reader/ReadingModeToggle.test.tsx`

**Failing test** asserts `data-state="off"` + text `Reading mode` off state; `data-state="on"` + text contains `Reading` and `✓` on; click fires `onToggle`.

**Implementation** — `<button>` with `aria-label="Reading mode"`, `data-state`, conditional styling (pill, `var(--ink-0)` bg when on, `var(--paper-1)` when off). Run → PASS.

**Commit** `Slice R4 T2: ReadingModeToggle pill with data-state`

---

## T3 — `PacingLabel`

**Files**
- Create: `frontend/src/components/reader/PacingLabel.tsx`
- Test: `frontend/src/components/reader/PacingLabel.test.tsx`

**Test** asserts `data-testid="pacing-label"` and matches `/^stave (one|two|three|four|five|six|seven|eight|nine|ten|\d+) · of (one|two|three|four|five|six|seven|eight|nine|ten|\d+)$/i` for pairs `(1,5)`, `(12,20)`, `(3,3)`.

**Implementation** `ORDINALS = ["One","Two",…,"Ten"]`.

**Commit** `Slice R4 T3: PacingLabel stave ordinal`

---

## T4 — `PageTurnArrow` + `ProgressHairline` + `ReadingModeLegend`

**Files**
- Create: `frontend/src/components/reader/PageTurnArrow.tsx` + test
- Create: `frontend/src/components/reader/ProgressHairline.tsx` + test
- Create: `frontend/src/components/reader/ReadingModeLegend.tsx` + test

**Tests:** testids `page-arrow-left`/`right` with click handlers, `aria-disabled` when disabled; `progress-hairline` with inner child `style.width = Math.round(progress*10000)/100 + '%'`, clamps `-0.5→"0%"`, `1.5→"100%"`; `reading-mode-legend` contains `ASKED`, `NOTED`, `ENTITY`.

**Commit** `Slice R4 T4: page arrows, progress hairline, legend`

---

## T5 — `NotePeekPopover`

**Files**
- Create: `frontend/src/components/reader/NotePeekPopover.tsx`
- Test: `frontend/src/components/reader/NotePeekPopover.test.tsx`

**Test** — given `{visible:true, body:"...", x:120, y:300}`, renders `data-testid="note-peek"` with the body. Hover-timing tested at integration (T8).

**Commit** `Slice R4 T5: NotePeekPopover presentational`

---

## T6 — `MarginColumn` `hidden` prop

**Files**
- Modify: `frontend/src/components/reader/MarginColumn.tsx`
- Modify: `frontend/src/components/reader/MarginColumn.test.tsx`

**Failing test:**
```tsx
it("renders aria-hidden and zero opacity when hidden prop is true", () => {
  render(<MarginColumn cards={[]} visibleSids={new Set()} focusedCardId={null}
    onBodyChange={() => {}} onBodyCommit={() => {}} hidden />);
  const el = screen.getByTestId("margin-column");
  expect(el.getAttribute("aria-hidden")).toBe("true");
  expect(el.style.opacity).toBe("0");
  expect(el.style.transform).toContain("translateX(40px)");
  expect(el.style.pointerEvents).toBe("none");
});

it("does not set aria-hidden when hidden prop is false/absent", () => {
  render(<MarginColumn cards={[]} visibleSids={new Set()} focusedCardId={null}
    onBodyChange={() => {}} onBodyCommit={() => {}} />);
  expect(screen.getByTestId("margin-column").getAttribute("aria-hidden")).not.toBe("true");
});
```

**Implementation** — add `hidden?: boolean`, merge styles conditionally. Preserve existing props/behavior.

**Commit** `Slice R4 T6: MarginColumn hidden prop with transition`

---

## T7 — `Sentence` emits `data-kind="note"` on noted spans

**Files**
- Modify (if not already): `frontend/src/components/reader/Sentence.tsx`
- Modify: `frontend/src/components/reader/Sentence.test.tsx`

**Test** — sentence with `marks=[{kind:"note", cardId}]` renders span with `data-kind="note"` and `data-sid`. Ask-only sentence does not carry `data-kind="note"`.

**Commit** `Slice R4 T7: Sentence data-kind=note for hover targets`

---

## T8 — ReadingScreen integration

**Files**
- Modify: `frontend/src/screens/ReadingScreen.tsx`
- Modify: `frontend/src/screens/ReadingScreen.test.tsx`

**Failing test additions (using RTL + mocked fetchChapter):**
- Toggle flips `data-reading-mode` on reader root.
- When on: pacing label, both arrows, progress hairline, legend are present; MarginColumn `aria-hidden="true"`.
- When off: those chrome elements are absent; MarginColumn visible.
- Toggle persists across remount for same bookId.
- Toggling twice returns DOM to baseline structure (no leaked listeners — verify by hovering after second toggle-off yields no peek).

**Implementation**
- Import `useReadingMode(bookId)`.
- `<div className="br" data-reading-mode={mode} …>`.
- Top-bar gets `style.opacity: mode === "on" ? 0.55 : 1` with 240ms transition.
- Stage applies ambient gradient background + widens when `mode === "on"` (update `gridTemplateColumns` to `1fr 0px` or shift margin offscreen; pass `hidden` to MarginColumn).
- Conditionally render `<PacingLabel num={chapter.num} total={chapter.total_chapters} />`, `<PageTurnArrow direction="left"/"right" onClick={turnBackward/turnForward} disabled={...} />`, `<ProgressHairline progress={progress} />`, `<ReadingModeLegend />` when `mode === "on"`.
- Hover delegation effect (only when mode on) on `bookRef`: `mouseover` → `closest('[data-kind="note"]')` → 150ms delay → find matching note card by `sid` → setPeek with body + anchor rect center. `mouseout` → clear timer + setPeek(null). Return cleanup removes listeners.
- Render `<NotePeekPopover visible={!!peek} body={peek?.body ?? ""} x={peek?.x ?? 0} y={peek?.y ?? 0} />`.

**Commit** `Slice R4 T8: integrate reading mode toggle and chrome into ReadingScreen`

---

## T9 — Playwright gate `slice-R4-reading-mode.spec.ts`

**Files**
- Create: `frontend/e2e/slice-R4-reading-mode.spec.ts`

1:1 with PRD ACs:
1. Toggle accessible name "Reading mode"; initial `data-state="off"`; after click `data-state="on"`, contains `✓` + "Reading".
2. Clicking toggles reader root `data-reading-mode` between `"off"` and `"on"`.
3. On: top-bar computed opacity `0.55`; margin column `aria-hidden="true"` + computed opacity `0`.
4. On: `[data-testid="pacing-label"]` text matches pacing regex.
5. On: `page-arrow-left` and `page-arrow-right` visible.
6. On: `progress-hairline` inner width equals computed formula.
7. On: `reading-mode-legend` contains `ASKED`/`NOTED`/`ENTITY`.
8. Off: above all absent; margin visible.
9. Reload restores per-book on-state from localStorage.
10. Two books isolated (toggle A on, navigate B → off; back to A → on).
11. On + hover `[data-kind="note"]` ≥150ms shows `note-peek` with note body; mouseleave hides.
12. Toggle twice (on→off) leaves no residual chrome and note-peek never appears on hover.

**Commit** `Slice R4 T9: e2e evaluator gate for reading mode`

---

## T10 — Full regression + screenshot capture

**Files**
- Create: `frontend/e2e/slice-R4-screenshots.spec.ts`

**Commands** — `npm test -- --run`, `npx playwright test slice-R4`, backend `pytest`.

**Commit** `Slice R4 T10: reading mode screenshots and regression pass`

---

## Dependencies

- T1 + T2 + T3 + T4 + T5 + T6 + T7 are independent or pairwise-independent → any order.
- T8 depends on T1–T7.
- T9 depends on T8.
- T10 depends on T9.

## Anticipated challenges

- **Opacity-after-transition** — Playwright reads must `expect.poll` or wait for the 260ms transition to settle.
- **Hover delegation teardown** — AC 12: toggling off must remove listeners; verify by attempting hover post-toggle-off and asserting no peek.
- **Per-book isolation under React Router** — navigating between `/books/a/read/1` and `/books/b/read/1` mounts a new ReadingScreen; bookId prop changes re-read localStorage.
- **Pacing regex** — middle dot `·` is `·`; confirm identical char in both component and test.

## Summary

10 tasks. 12 frontend files created (`useReadingMode.ts` + test, 6 components + tests, 2 e2e specs). 4 modified (`ReadingScreen.tsx` + test integration, `MarginColumn.tsx` + test for `hidden` prop, possibly `Sentence.tsx` + test for `data-kind="note"`). 0 backend changes. Playwright gate: `frontend/e2e/slice-R4-reading-mode.spec.ts`.
