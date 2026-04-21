# Slice 1 Review — scaffold-library

**Date:** 2026-04-21
**Verdict:** REVISE
**Reviewer:** Evaluator agent (superpowers:code-reviewer)

## Rubric check

1. Tests: PASS — backend `pytest tests/` → 906 passed, 0 failures (anaconda pytest). Frontend `npm test -- --run` → 21 passed across 8 files, 2 benign `act()` warnings only.
2. Dev server: PARTIAL — `npm run dev` starts and serves `/` with HTTP 200; `python main.py` starts; `curl http://localhost:8000/books` returns the Christmas Carol entry. **However `npm run build` fails with 2 TypeScript errors** (see findings). Could not visually verify the rendered screen; based verdict on the fact that the build pipeline is broken.
3. Config drift: PASS — CORS already included `http://localhost:5173`; no new env vars introduced; no auth changes.
4. Acceptance criteria: FAIL — criterion 4 is only partially satisfied (`BookCover` is rendered with `title=""`, so the in-cover title does not appear; card-level title below the cover is fine).
5. Scope: PASS — the Generator stayed inside the PRD's in-scope list. No new features, abstractions, or out-of-scope components were added.

## Per-criterion verification

1. **"Running `npm run dev` inside `frontend/` starts the Vite dev server on port 5173 without console errors."**
   - PASS — `curl http://localhost:5173/` returns HTTP 200 with Vite-injected hot-reload index.html.

2. **"Navigating to `http://localhost:5173/` renders the Library screen: top NavBar with the *Book*/*rag* wordmark, "Your shelf" header, and a grid of book cards."**
   - PASS (verifiable via tests) — `App.test.tsx` asserts "your shelf" and "Library" render at `/`; `LibraryScreen.test.tsx` asserts NavBar tabs, shelf header, and BookCard grid render after fetch success. Could not visually confirm in a browser.

3. **"The Library fetches `GET http://localhost:8000/books` on mount and renders one `BookCard` per returned book. A loading state is visible before the response arrives; a readable error state is visible if the fetch fails."**
   - PASS — `LibraryScreen.test.tsx` covers all three states (loading, success w/ one card, error 500 → "Couldn't load your books"). `api.test.ts` verifies the fetch URL is `http://localhost:8000/books`.

4. **"*A Christmas Carol* (book_id `christmas_carol_e6ddcd76`) appears as a card with: a generated two-tone cover (via `BookCover`), a title, a progress pill or bar, and chapter progress text (e.g. "1 of 3")."**
   - PARTIAL / FAIL — Live `curl /books` returns `{"book_id": "christmas_carol_e6ddcd76", "title": "Christmas Carol", "total_chapters": 3, "current_chapter": 3, ...}`. The `BookCard` renders the card-level title (serif italic below the cover) and the progress pill correctly. **But the `BookCover` inside the card receives `title=""` (`frontend/src/components/BookCard.tsx:28`)**, so the cover art is generated without the "Christmas Carol" overlay that the handoff (`design-handoff/project/components.jsx:230`) specifies. The cover still shows the "a novel" caption, the border, and the mood-derived color, so it is "a generated two-tone cover" — but it is not the cover the handoff designed.

5. **"Only books whose `pipeline_state.json` has `ready_for_query: true` appear in the Library — in-progress or failed ingestions are excluded."**
   - PASS — `tests/test_books_endpoint.py::test_excludes_not_ready_books` verifies. Live run confirms: the seven orphan directories in `data/processed/` are skipped with WARNING logs, only `christmas_carol_e6ddcd76` is returned.

6. **"The design tokens from `design-handoff/project/tokens.css` are loaded globally and the page visibly uses the linen paper palette and Lora/IBM Plex Sans typography."**
   - PASS — `diff design-handoff/project/tokens.css frontend/src/styles/tokens.css` returns no output (verbatim copy). `index.html` preconnects Google Fonts and loads IBM Plex Sans + Lora; `main.tsx` imports `./styles/tokens.css` once at root. Components reference `var(--serif)` and `var(--sans)`.

7. **"The backend endpoint `GET /books` is callable directly (e.g. `curl http://localhost:8000/books`) and returns a JSON array matching the `Book` contract below."**
   - PASS — Live `curl http://localhost:8000/books | jq .` returns a 1-element array with all five contract fields, typed correctly. Title is correctly derived: `christmas_carol_e6ddcd76` → "Christmas Carol".

8. **"`pytest -v` passes with at least one test covering `GET /books` (empty case and a case with one ready book on disk)."**
   - PASS — `tests/test_books_endpoint.py` has 8 tests: empty, one-ready-book, default current_chapter, excludes not-ready, skips orphan dirs, skips corrupt state, title-preserves-no-suffix, title-only-strips-8-hex. All pass.

9. **"No existing backend tests regress."**
   - PASS — full run: 906 passed, 0 failed, 0 errors, 5 deprecation warnings unrelated to this slice.

10. **"The NavBar shows *Library* as the active item; the *Reading* and *Upload* tabs are visible but do nothing (no routing yet) and clicking them does not throw."**
    - PASS — `NavBar.tsx` sets `aria-current="page"` and `data-active="true"` only on the active tab, and `onClick={(e) => e.preventDefault()}` on every tab. `NavBar.test.tsx` has a userEvent test that clicks Reading and Upload and asserts nothing throws and Library remains active.

## Findings

1. **Critical — `npm run build` fails.** Running `npm run build` (which the PRD does not explicitly require, but which is the de-facto "production-ready" check) produces two TypeScript errors:

   ```
   vite.config.ts(7,3): error TS2769: No overload matches this call.
     Object literal may only specify known properties, and 'test' does not exist in type 'UserConfigExport'.
   src/screens/LibraryScreen.test.tsx(2,32): error TS6133: 'beforeEach' is declared but its value is never read.
   ```

   Fixes:
   - `frontend/vite.config.ts` — change `import { defineConfig } from "vite"` to `import { defineConfig } from "vitest/config"`, or split the Vitest config into a separate `vitest.config.ts`. (The PRD plan had the same faulty line, so this is a plan-level oversight the Generator inherited; still, the Generator accepted a broken build.)
   - `frontend/src/screens/LibraryScreen.test.tsx:2` — remove the unused `beforeEach` import (only `afterEach` is used).

   Once fixed, please re-run `npm run build` and confirm exit 0 before declaring the slice done. The dev server works today, but a broken build means the frontend cannot be packaged for any downstream slice that needs a built artifact.

2. **Important — `BookCard` renders `BookCover` with `title=""` to placate the test.** `frontend/src/components/BookCard.tsx:28` passes an empty string instead of the real `title`. The Generator flagged this as a known deviation. The root cause is `BookCard.test.tsx` uses `screen.getByText("Christmas Carol")` which would throw if the title appeared both inside the cover and below it. The correct fix is to repair the test (not the product code):

   ```tsx
   // frontend/src/components/BookCard.test.tsx — example fix
   import { render, screen, within } from "@testing-library/react";
   // ...
   it("renders title, progress pill, and chapter-progress text", () => {
     const { container } = render(<BookCard book_id="christmas_carol_e6ddcd76" title="Christmas Carol" total_chapters={3} current_chapter={1} />);
     const matches = screen.getAllByText("Christmas Carol");
     expect(matches.length).toBeGreaterThanOrEqual(1);
     expect(screen.getByText("1")).toBeInTheDocument();
     expect(screen.getByText(/of\s*3/i)).toBeInTheDocument();
   });
   ```

   Or scope with a `data-testid="book-card-title"` on the card-level title `<div>`, then `within(screen.getByTestId("book-card-title")).getByText("Christmas Carol")`.

   Then revert `BookCard.tsx` line 28 to `<BookCover book_id={book_id} title={title} />` so the cover renders the intended handoff design (title overlay on the generative cover). This restores criterion 4's "generated two-tone cover".

   Why this matters beyond slice 1: slices 2, 3, 4 will render `BookCover` + a separate title in more places (Reading screen header, Upload result tile, etc.). If the team normalizes "strip the title from the cover to make getByText happy", every future cover will look wrong. The compounding cost makes this a REVISE-level concern now rather than a TODO later.

3. **Minor — `ProgressPill` has a latent ambiguity that will bite when `current === total`.** The component renders `<span>{current}</span>` and `<span>of {total}</span>`. When a book is fully read (e.g. Christmas Carol today with `current_chapter=3, total_chapters=3`), `getByText("3")` would match both spans. The live endpoint currently returns `current_chapter: 3`, so a future test that checks "3 of 3" via `getByText("3")` will throw. The tests on disk today use `2 of 3` and `1 of 3`, so they pass. Worth fixing defensively (e.g. wrap `{current}` in a `data-testid="progress-current"`), but not a blocker for this slice.

4. **Minor — `npm test` emits two `act()` warnings** from `LibraryScreen` and `App` tests that unmount while a pending fetch still settles. Tests pass, but the warnings will clutter CI output. Wrapping the success-path assertions in `await waitFor(...)` or using `findByText` end-to-end would silence them.

## If APPROVE

(Not applicable — verdict is REVISE.)

## Minimal revision checklist for the Generator

- [ ] Fix `frontend/vite.config.ts` so `tsc -b` passes (use `vitest/config`'s `defineConfig` or move test config to a separate file).
- [ ] Remove the unused `beforeEach` import from `frontend/src/screens/LibraryScreen.test.tsx:2`.
- [ ] Fix `frontend/src/components/BookCard.test.tsx` to tolerate the title appearing twice (`getAllByText` or scope with `within` / `data-testid`).
- [ ] Revert `frontend/src/components/BookCard.tsx:28` to `<BookCover book_id={book_id} title={title} />`.
- [ ] Re-run `cd frontend && npm run build && npm test -- --run` and `/Users/jeffreykrapf/anaconda3/bin/pytest tests/ --tb=short -q`; all three must pass.
- [ ] Commit with a message noting the build fix and the BookCard/BookCover workaround revert.
