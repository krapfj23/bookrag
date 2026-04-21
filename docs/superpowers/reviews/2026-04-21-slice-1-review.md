# Slice 1 Review — scaffold-library

**Date:** 2026-04-21
**Verdict:** APPROVE
**Reviewer:** Evaluator agent (superpowers:code-reviewer)

## Rubric check

1. Tests: PASS — backend `pytest tests/` → 906 passed, 0 failures (anaconda pytest). Frontend `npm test -- --run` → 21 passed across 8 files, 1 benign `act()` warning only.
2. Dev server: PASS — `npm run build` now exits 0 (tsc -b clean, vite build emits `dist/index.html` + CSS + JS bundles). `npm run dev` starts, `python main.py` starts, `curl http://localhost:8000/books` returns the Christmas Carol entry.
3. Config drift: PASS — CORS already included `http://localhost:5173`; no new env vars introduced; no auth changes.
4. Acceptance criteria: PASS — criterion 4 is now fully satisfied. `BookCard` passes `title={title}` to `BookCover` so the cover overlay renders as the handoff designed.
5. Scope: PASS — the Generator stayed inside the PRD's in-scope list. The revision commit touched only the four files called out in the prior review.

## Per-criterion verification

1. **"Running `npm run dev` inside `frontend/` starts the Vite dev server on port 5173 without console errors."**
   - PASS — Vite dev server starts; `npm run build` also exits 0 now, so the frontend can be packaged for downstream slices.

2. **"Navigating to `http://localhost:5173/` renders the Library screen: top NavBar with the *Book*/*rag* wordmark, "Your shelf" header, and a grid of book cards."**
   - PASS (verifiable via tests) — `App.test.tsx` asserts "your shelf" and "Library" render at `/`; `LibraryScreen.test.tsx` asserts NavBar tabs, shelf header, and BookCard grid render after fetch success.

3. **"The Library fetches `GET http://localhost:8000/books` on mount and renders one `BookCard` per returned book. A loading state is visible before the response arrives; a readable error state is visible if the fetch fails."**
   - PASS — `LibraryScreen.test.tsx` covers all three states (loading, success w/ one card, error 500 → "Couldn't load your books"). `api.test.ts` verifies the fetch URL is `http://localhost:8000/books`.

4. **"*A Christmas Carol* (book_id `christmas_carol_e6ddcd76`) appears as a card with: a generated two-tone cover (via `BookCover`), a title, a progress pill or bar, and chapter progress text (e.g. "1 of 3")."**
   - PASS — `BookCard.tsx:28` now passes `title={title}` to `BookCover`, so the cover renders with the intended title overlay plus the "a novel" caption. The card-level title (serif italic below the cover) and progress pill still render. Tests tolerate the title appearing in both places via `getAllByText`.

5. **"Only books whose `pipeline_state.json` has `ready_for_query: true` appear in the Library — in-progress or failed ingestions are excluded."**
   - PASS — `tests/test_books_endpoint.py::test_excludes_not_ready_books` verifies. Live run confirms: orphan directories in `data/processed/` are skipped with WARNING logs, only `christmas_carol_e6ddcd76` is returned.

6. **"The design tokens from `design-handoff/project/tokens.css` are loaded globally and the page visibly uses the linen paper palette and Lora/IBM Plex Sans typography."**
   - PASS — `design-handoff/project/tokens.css` is a verbatim copy of `frontend/src/styles/tokens.css`. `index.html` preconnects Google Fonts and loads IBM Plex Sans + Lora; `main.tsx` imports `./styles/tokens.css` once at root. Components reference `var(--serif)` and `var(--sans)`.

7. **"The backend endpoint `GET /books` is callable directly (e.g. `curl http://localhost:8000/books`) and returns a JSON array matching the `Book` contract below."**
   - PASS — Live `curl http://localhost:8000/books | jq .` returns a 1-element array with all five contract fields, typed correctly. Title is correctly derived: `christmas_carol_e6ddcd76` → "Christmas Carol".

8. **"`pytest -v` passes with at least one test covering `GET /books` (empty case and a case with one ready book on disk)."**
   - PASS — `tests/test_books_endpoint.py` has 8 tests: empty, one-ready-book, default current_chapter, excludes not-ready, skips orphan dirs, skips corrupt state, title-preserves-no-suffix, title-only-strips-8-hex. All pass.

9. **"No existing backend tests regress."**
   - PASS — full run: 906 passed, 0 failed, 0 errors, 5 deprecation warnings unrelated to this slice.

10. **"The NavBar shows *Library* as the active item; the *Reading* and *Upload* tabs are visible but do nothing (no routing yet) and clicking them does not throw."**
    - PASS — `NavBar.tsx` sets `aria-current="page"` and `data-active="true"` only on the active tab, and `onClick={(e) => e.preventDefault()}` on every tab. `NavBar.test.tsx` has a userEvent test that clicks Reading and Upload and asserts nothing throws and Library remains active.

## Findings

All prior findings resolved. No new regressions introduced.

1. **(Resolved) `npm run build` now passes.** `vite.config.ts` imports `defineConfig` from `"vitest/config"` so the `test` block is typed. The unused `beforeEach` import was removed from `LibraryScreen.test.tsx`. `tsc -b && vite build` exits 0 and emits a 151 KB JS bundle + 5 KB CSS.

2. **(Resolved) `BookCard` passes the real title to `BookCover`.** Line 28 now reads `<BookCover book_id={book_id} title={title} />`. The tests in `BookCard.test.tsx` and `LibraryScreen.test.tsx` were updated to use `getAllByText("Christmas Carol").length >= 1` since the title now appears in both the cover overlay and the card-level label below it. This is the correct fix direction — adjust the tests, keep the product code faithful to the handoff.

3. **(Unchanged, still minor, still not a blocker) `ProgressPill` latent ambiguity when `current === total`.** Out of scope for this slice; fold into slice 2 or later when the Reading screen exercises finished books.

4. **(Unchanged, still minor, still not a blocker) One `act()` warning from `LibraryScreen.test.tsx`.** The suite still passes; silencing via `findByText` or explicit `waitFor` is a nice-to-have for a future cleanup slice.

## If APPROVE

**One-sentence slice summary for the backlog:**
Scaffolds a React + Vite frontend that renders the Library screen by fetching `GET /books` (a new backend endpoint that reads `pipeline_state.json` and returns only `ready_for_query` books), wires in the design-handoff tokens and fonts, and ships 21 frontend tests plus 8 backend endpoint tests — all green, with a clean production build.

## Revision notes

The REVISE loop produced a single focused commit `d20f5b1` that addressed every finding from the prior review:

- **Finding 1a (critical): vite.config.ts TS2769.** Fixed by switching `import { defineConfig } from "vite"` to `import { defineConfig } from "vitest/config"`. The latter's config type includes the `test` block, so the overload now matches. Verified `npm run build` exits 0.
- **Finding 1b (critical): LibraryScreen.test.tsx TS6133 unused `beforeEach`.** Fixed by removing `beforeEach` from the vitest imports list. `grep beforeEach` on the file now returns no hits.
- **Finding 2 (important): BookCard passing `title=""` to BookCover.** Fixed by restoring `title={title}` on `BookCard.tsx:28` and updating the two affected tests (`BookCard.test.tsx` and `LibraryScreen.test.tsx`) to use `getAllByText("Christmas Carol").length >= 1` instead of `getByText("Christmas Carol")`. This accepts that the title appears both in the cover overlay and the card-level label, which is what the handoff designed.
- **Findings 3 & 4 (minor):** Not in scope for this REVISE — carried forward as notes for future slices.

No new files, no new dependencies, no collateral changes. Five insertions, five deletions across four files. All 906 backend tests and 21 frontend tests still pass, and the production build is now clean. Verdict flips from REVISE to APPROVE.
