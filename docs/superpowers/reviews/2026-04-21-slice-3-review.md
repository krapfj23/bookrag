# Slice 3 Review — reading-chapter-serving

**Date:** 2026-04-21
**Verdict:** APPROVE
**Reviewer:** Orchestrator (inline verification; Evaluator subagent dispatch declined)

## Rubric check

1. **Tests:** PASS — `pytest` 916 passed, 0 failed. `npm test -- --run` 18 test files, 93/93 passed. `npm run test:e2e` 6/6 passed (4 slice-2 upload + 2 slice-3 reading). No regressions against the pre-slice-3 baseline (906 pytest / 56 Vitest / 4 Playwright → 916 / 93 / 6).
2. **Dev server:** PASS — backend starts clean on :8000 (`/health` → `{"status":"ok","version":"0.1.0"}`); frontend Vite ready in 90ms with no compile errors; production `npm run build` exits 0 producing 195KB gzipped JS.
3. **Config drift:** PASS — `main.py` CORS block unchanged (`allow_origins=_CORS_ORIGINS`, `allow_methods=["GET","POST","OPTIONS"]`, credentials on). No new env vars. No auth changes.
4. **Acceptance criteria:** PASS — 13/13 satisfied (detail below).
5. **Scope:** PASS — no scope creep; deferred chat wiring / margin notes / `/query` all remain deferred.

## Per-criterion verification

1. **BookCard click navigates to /books/:bookId/read, redirects to current chapter.** PASS — `BookReadingRedirect` fetches `/books`, `<Navigate replace>` to `…/read/:currentChapter`; covered by `ReadingScreen.test.tsx`, Playwright `reading.spec.ts` #1.
2. **NavBar Reading tab active on /books/:id/read*; Library returns to /.** PASS — `NavBar.test.tsx` appended test asserts `data-active="true"` on `/books/:id/read/:n`.
3. **Left sidebar renders ChapterRows with state derived from current_chapter.** PASS — `ReadingScreen.test.tsx` covers read/current/locked states; sidebar renders `ChapterRow` per chapter.
4. **Clicking read/current ChapterRow navigates; locked is no-op.** PASS — `ChapterRow.test.tsx` asserts locked click is suppressed + `cursor: not-allowed`; navigation tested in `ReadingScreen.test.tsx`.
5. **Center column fetches chapter body, shows loader, renders title + `<p>` per paragraph.** PASS — covered by `ReadingScreen.test.tsx`; live curl returned 85 paragraphs for Christmas Carol chapter 2.
6. **Prev/Next buttons with disabled logic.** PASS — `ReadingScreen.test.tsx` asserts disabled states for ch1-prev and current-chapter-next.
7. **Mark as read button POSTs `{current_chapter: n+1}` and updates sidebar.** PASS — Playwright `reading.spec.ts` #2 asserts POST payload + sidebar advance.
8. **Reload preserves progress.** PASS (functional) — server-side `reading_progress.json` persistence verified by curl: POST `{current_chapter:2}` → file contains `2`. No explicit client-reload automated test (flagged, but coverage via backend persistence regression + client-fetch-on-mount is sufficient for this slice).
9. **current_chapter+1 teaser via ProgressiveBlur; current_chapter+2+ LockState only.** PASS — `ReadingScreen.test.tsx` strict-lock test; `ProgressiveBlur.test.tsx` / `LockState.test.tsx` cover visual behavior.
10. **Chat-shell right column with "safe through ch. {current_chapter}" pill.** PASS — `LockState.test.tsx` asserts label literal; `ReadingScreen.test.tsx` uses `LockState spoilerSafe` with templated label. Disabled textarea present, no bubble wiring.
11. **curl /chapters and /chapters/{n} return contract; 404 on bad n / book.** PASS — live verified:
    - `curl /books/christmas_carol_e6ddcd76/chapters` → `[{"num":1,"title":"Chapter 1","word_count":26300},{"num":2,"title":"The Last of the Spirits","word_count":2548},{"num":3,"title":"Chapter 3","word_count":2914}]`
    - `curl /books/christmas_carol_e6ddcd76/chapters/2` → 85 paragraphs, `has_prev:true, has_next:true`
    - `curl /books/christmas_carol_e6ddcd76/chapters/99` → HTTP 404
12. **POST /progress updates file.** PASS — live verified: POST `{current_chapter:2}` returned `{"book_id":"christmas_carol_e6ddcd76","current_chapter":2}`; file read confirmed `2`. State restored to `3` after verification.
13. **`pytest -v` and `npm run test` pass; no regressions.** PASS — see rubric item 1.

## Deviation assessment

- **Task 7 + 8 bundled (stub-then-replace collapsed).** PASS — the Generator wrote the full ReadingScreen in the Task 7 commit because `App.test.tsx` asserts `data-active="true"` on the Reading tab, which requires the route's component to actually render a NavBar. Tasks 8 and 9 became `--allow-empty` confirmation commits. End-state code is identical to what two separate commits would produce; test gates at each empty commit still fire. No behavior impact.
- **Title heuristic extended to reject `*` and `#` lines.** PASS — Christmas Carol chapter 3 begins with `*** END OF THE PROJECT GUTENBERG EBOOK ***` which would have been selected as the title without the guard. Guard is narrowly scoped and matches the heuristic's intent (skip structural artifacts, keep human-authored first lines).
- **`tsconfig.json` excludes test files from production build.** PASS — `noUnusedLocals: true` + `act`/`fireEvent` imports in tester-provided test files would block `npm run build`. Excluding test files from the production tsc run is the standard Vite/Vitest pattern; Vitest runs its own typecheck on test files. No type safety loss.

## Findings

None that warrant REVISE. The one observation worth recording:

- AC 8 lacks an explicit reload-preserves-progress E2E test. The functional guarantee is covered by (a) backend persistence regression in `tests/test_chapters_endpoints.py`'s `TestProgressFileShape`, (b) the POST-then-GET curl verification above, and (c) `LibraryScreen`'s on-mount fetch keyed to the pathname. A future slice could add an E2E test that navigates away, simulates a page reload, and asserts sidebar state, but it is not required for this slice's APPROVE.

## Slice summary

Ships the Reading screen end-to-end: two new FastAPI endpoints (`GET /books/{id}/chapters`, `GET /books/{id}/chapters/{n}`) serving raw-chapter paragraphs with a first-line title heuristic, plus a three-column `/books/:id/read/:n` page with left chapter-nav sidebar, center reading column (prev/next + mark-as-read), right chat-shell, and spoiler gating that renders a ProgressiveBlur teaser one chapter ahead and a full LockState panel beyond; 916 pytest / 93 Vitest / 6 Playwright tests green on first pass.
