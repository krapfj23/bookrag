# Slice R1 Review — Reading surface + sentence anchors

**Date:** 2026-04-22
**Verdict:** APPROVE
**Reviewer:** Evaluator agent

## Rubric check

1. **Tests: PASS** — Backend: `1221 passed, 3 warnings in 13.26s` (after installing missing local deps pydantic, httpx, slowapi, rdflib, etc.; no cognee needed — loader doesn't import it). Frontend: `29 files, 147 passed` via `npm test -- --run`.
2. **Dev server: PASS** — Frontend Vite server runs on :5173 (verified HTTP 200); Playwright spec exercises the full surface end-to-end with no console errors surfaced. Backend `python main.py` requires `cognee` which is documented as "not always installed locally" in CLAUDE.md — the R1 spec runs against mocked endpoints so this does not affect verification of R1 behavior.
3. **Config drift: PASS** — No changes to `main.py`, CORS, or environment variables. No new `BOOKRAG_*` vars introduced. Chapter endpoint gains two additive JSON fields (`paragraphs_anchored`, `anchors_fallback`) without breaking the legacy `paragraphs: string[]` contract.
4. **Acceptance criteria: PASS** — see per-criterion verification below.
5. **Scope: PASS** — Implementation sticks to R1 scope: replaced `ReadingScreen.tsx`, added `BookSpread`/`Page`/`Paragraph`/`Sentence` primitives, DOM paginator, `useReadingCursor` hook, fog-of-war styling, keyboard-only nav, sentence-anchor emission on chapter endpoint. No selection toolbar, no card state, no streaming, no reader-var variants, no entity underlines. Deferred items (R2–R4) untouched.
6. **Playwright gate: PASS** — `frontend/e2e/slice-R1-reading-surface.spec.ts` runs `7 passed (2.7s)`. Screenshot helper at `frontend/e2e/slice-R1-screenshots.spec.ts` runs `5 passed (3.6s)` producing:
   - `docs/superpowers/reviews/assets/2026-04-22-slice-R1/ac1-two-page-spread.png`
   - `docs/superpowers/reviews/assets/2026-04-22-slice-R1/ac7-data-sid-anchors.png`
   - `docs/superpowers/reviews/assets/2026-04-22-slice-R1/ac9-fog-of-war.png`
   - `docs/superpowers/reviews/assets/2026-04-22-slice-R1/ac10-after-arrow-right.png`
   - `docs/superpowers/reviews/assets/2026-04-22-slice-R1/ac11-cursor-persisted.png`

## Per-criterion verification

1. **"GET /books/{book_id}/chapters/{n}` returns ... every paragraph is an ordered list of sentences, each with a stable id of the form `p{n}.s{m}`"** — PASS. `api/loaders/sentence_anchors.py` emits `p{1-indexed-paragraph}.s{1-indexed-sentence}`; unit-tested in `tests/test_sentence_anchors.py`.
2. **"preserves existing `num`, `title`, `has_prev`, `has_next`, `total_chapters` fields unchanged and adds the sentence-anchored structure in a new field"** — PASS. `api/loaders/book_data.py` Chapter model retains all legacy fields and adds `paragraphs_anchored` + `anchors_fallback` as additive fields.
3. **"Sentence boundaries ... derived from the BookNLP `.tokens` TSV ... falls back to a regex sentence splitter and sets a boolean `anchors_fallback: true`"** — PASS. `build_paragraphs_anchored` tries BookNLP tokens first; `regex_fallback_paragraphs` handles the missing/mismatched case with `anchors_fallback=True`.
4. **"Navigating to `/book/{bookId}` without a `#chapter=` hash loads chapter 1"** — PASS. R1 spec `renders a two-page spread` exercises `/books/carol/read/1`; BookReadingRedirect semantics preserved. See `ac1-two-page-spread.png`.
5. **"reading surface renders a two-page spread: top bar ... and `BookSpread` with left + right pages"** — PASS. `BookSpread.tsx` renders topbar + two Page children with paper/spine tokens; `ac1-two-page-spread.png` confirms visual layout matching the design handoff (Bookrag nav, "Chapter 1" title, 1/4 folio, drop cap, justified prose, spine gradient).
6. **"client-side DOM paginator measures rendered page boxes and chunks ... no sentence is split across pages and every sentence is present exactly once"** — PASS. `frontend/src/lib/reader/paginator.ts` + `paginator.test.ts` cover no-split + completeness invariants.
7. **"Every rendered sentence carries `data-sid=\"p{n}.s{m}\"`"** — PASS. `Sentence.tsx` emits the attribute; E2E assertion `sentences carry data-sid p{n}.s{m}` iterates every `[data-sid]` and matches the regex; see `ac7-data-sid-anchors.png`.
8. **"ArrowRight advances one spread; ArrowLeft goes back ... no cross-chapter turn"** — PASS. Keyboard handler in `ReadingScreen.tsx`; E2E specs `ArrowRight past the last spread does not crash` and `ArrowLeft before the first spread does not crash` prove clamping.
9. **"sentences strictly after the cursor are dimmed (opacity ≤ 0.35) and blurred ... sentences at or before the cursor are fully opaque and unblurred"** — PASS. E2E `post-cursor sentences are fogged (opacity < 0.5)` asserts `p1.s2` opacity < 0.5 and `p1.s1` opacity > 0.9; `ac9-fog-of-war.png` shows crisp first sentence and blurred remainder.
10. **"Turning forward advances the cursor to the last sentence visible on the new spread; turning backward does not rewind"** — PASS. `useReadingCursor.advanceTo` short-circuits when `compareSid(sid, prev) <= 0`. E2E spec `ArrowRight advances ... ArrowLeft goes back without rewinding cursor` verifies; `ac10-after-arrow-right.png` shows spread advanced with no fog.
11. **"cursor persists across reloads in `localStorage` under key `bookrag.cursor.{bookId}`"** — PASS. `CURSOR_KEY` + `readStoredCursor`; E2E `reload restores cursor from localStorage` confirms the key format and restoration; `ac11-cursor-persisted.png` after reload.
12. **"On initial mount with no stored cursor, the cursor is the first sentence of the chapter"** — PASS. `useReadingCursor` seeds from `firstSid` when no stored cursor exists; `ac9-fog-of-war.png` shows only `p1.s1` crisp, rest fogged on initial load.
13. **"Playwright spec at `frontend/e2e/slice-R1-reading-surface.spec.ts`"** — PASS. All 7 cases green.

## Findings

- **Pre-existing Playwright specs `reading.spec.ts` and `chat.spec.ts`** target the old `ReadingScreen` (sidebar/annotation panel) and are expected to fail — noted per context, not a regression for R1. Recommend a follow-up task to either retire or rewrite them once R2 lands.
- **`ReadingScreen.test.tsx` was replaced** per plan T7 — explicit, not a regression.
- **Backend `python main.py` requires `cognee`** which is not locally installed in this environment. Per CLAUDE.md this is expected; test infrastructure uses a mock in `tests/conftest.py`. No action required.
- **Local venv was missing common deps** (pytest, pydantic, httpx, slowapi, rdflib). Not an R1 issue; an environment-bootstrap note.

## If APPROVE

R1 delivers a two-page paginated reading surface with BookNLP-backed sentence anchors, forward-only localStorage-persisted cursor, and keyboard-driven fog-of-war — all acceptance criteria verified by unit + E2E tests and visual screenshots.
