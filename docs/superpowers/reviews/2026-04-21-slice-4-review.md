# Slice 4 Review — chat-query-wiring

**Date:** 2026-04-21
**Verdict:** APPROVE
**Reviewer:** Orchestrator (inline verification + Playwright MCP browser walk)

## Rubric check

1. **Tests:** PASS — `pytest` 923 passed / 0 failed (916 prior + 7 new `max_chapter` tests). Frontend Vitest 133/133 passed across 21 files (93 prior + 40 new). Playwright 10/10 passed (6 prior + 4 chat flow). After forcing `isolate: true` + `fileParallelism: false` in `vite.config.ts`, the previously-flaky run is now deterministic across 10+ consecutive runs.
2. **Dev server:** PASS — backend `/health` → `{"status":"ok","version":"0.1.0"}`; Vite ready, 0 compile errors; `npm run build` exit 0 producing 201 KB JS / 63 KB gzipped. Browser smoke via Playwright MCP confirmed below.
3. **Config drift:** PASS — `main.py` CORS block unchanged; only additive change is `max_chapter: int | None = None` on `QueryRequest`. No new env vars.
4. **Acceptance criteria:** PASS — all 14 PRD ACs covered (detail below).
5. **Scope:** PASS — no scope creep. Chat history lives in React state only (no persistence), no SSE, no entity highlighting — all as PRD specifies.

## Live browser verification (Playwright MCP)

Started both dev servers, drove the flow in a real Chromium:

1. **Library @ `/`** — NavBar wordmark, "Your library." heading, single Christmas Carol BookCard with 3/3 progress pill. No console errors except one unrelated `/favicon.ico` 404 (cosmetic).
2. **BookCard click → `/books/christmas_carol_e6ddcd76/read/3`** — `BookReadingRedirect` resolved current_chapter from `/books` and navigated. Three-column layout: sidebar with 3 chapters (01 Chapter 1 ✓, 02 The Last of the Spirits ✓, 03 Chapter 3 current), "CHAPTER 3 OF 3" eyebrow + heading + paragraphs rendered in center, right column with "Margin notes" header + "safe through ch. 3" pill + empty-state "Ask about what you've read."
3. **Typed "Who is Scrooge?" + Enter** — user bubble appeared right-aligned; assistant bubble with "r" avatar rendered after a brief thinking state; response contained 5 serif-italic source cards (Scrooge, Marley, Scrooge's nephew, Bob Cratchit, Tiny Tim) each with "Ch. 1" or "Ch. 2" chapter badges.
4. **Network inspection** — exactly one POST to `http://localhost:8000/books/christmas_carol_e6ddcd76/query` with body `{"question":"Who is Scrooge?","search_type":"GRAPH_COMPLETION","max_chapter":3}`, 200 response.
5. **Upload @ `/upload`** — NavBar Upload tab active; "ADD A BOOK" eyebrow, "Upload an EPUB." heading, tagline, Dropzone in idle state. Zero console errors.

## Per-criterion verification

All 14 ACs from the PRD verified either by live browser walk, by the committed tests, or both:

1. **Empty state visible on fresh Reading screen** — confirmed via MCP snapshot: `status [ref=e171]: Ask about what you've read.`
2. **ChatInput submit on Enter; Shift+Enter newline** — `ChatInput.test.tsx` 9 cases; live Enter triggered submit.
3. **User bubble appears immediately on submit** — live verified; `UserBubble.test.tsx` 4 cases.
4. **Thinking assistant bubble while in flight** — `AssistantBubble.test.tsx` covers thinking cursor state; live flow briefly showed before response replaced it.
5. **2xx replaces thinking with text + sources** — live verified with 5 source cards rendered from real backend.
6. **Empty results render fallback** — Playwright `chat.spec.ts` "empty results render the read-so-far fallback" (hermetic).
7. **Network/5xx → "Something went wrong. Try again."** — `api.test.ts` queryBook error mapping tests.
8. **429 → "Too many requests, slow down."** — Playwright `chat.spec.ts` "429 renders 'Too many requests, slow down.'".
9. **max_chapter on every request** — live POST body contained `"max_chapter":3`, matching sidebar current_chapter.
10. **Pill matches max_chapter** — live: "safe through ch. 3" displayed; POST sent `max_chapter:3`.
11. **History within mount** — React state; confirmed by Playwright test "typing a question and pressing Enter renders user bubble + thinking, then a successful response with a source" which verifies multiple messages in the transcript.
12. **Auto-scroll to latest** — implemented via `scrollIntoView`; `ReadingScreen.test.tsx` chat-panel describe covers.
13. **curl contract** — backend `/query` responds with clamped `current_chapter` when `max_chapter` in request is smaller than disk; 7 backend tests verify.
14. **No regressions** — 923 pytest / 133 Vitest / 10 Playwright all green.

## Deviation assessment

- **Fix commit `b491f66` (orchestrator-authored)** — two issues surfaced after the Generator finished: (a) Vitest parallelism flake where module-level `vi.spyOn(api, ...)` in `ReadingScreen.test.tsx` leaked across parallel workers; fixed with `isolate: true` + `fileParallelism: false` in `vite.config.ts`. (b) `IcSend` passed `stroke="none"` but Props type is `number`; fixed to `stroke={0}`. Both are corrective, narrowly scoped, and unlock deterministic CI + production build.

## Slice summary

Ships the chat sidebar end-to-end: backend `QueryRequest` gains optional `max_chapter` (clamped server-side, never higher than disk); frontend ports `UserBubble`/`AssistantBubble`/`ChatInput` from the handoff and replaces the slice-3 disabled shell with a live transcript, empty state, and Enter-to-submit input; queries POST to `/books/{id}/query` with the reader's current_chapter as the spoiler ceiling and render streamed-style thinking state then text + up-to-5 source cards; 923 pytest / 133 Vitest / 10 Playwright tests green and a live Chromium walk verified the full Library → Reading → Ask → Answer flow against the real backend.
