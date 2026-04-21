# Slice 4 — chat-query-wiring PRD

**Date:** 2026-04-21
**Parent spec:** ../specs/2026-04-21-frontend-integration-agent-pipeline-design.md

## Goal

Wire the disabled chat-shell in `ReadingScreen` to the live `POST /books/{book_id}/query` endpoint so readers can ask spoiler-safe questions about what they've read, scoped by `current_chapter`, and see assistant responses with source citations inline.

## User stories

- As a reader, I can type a question and press Enter so that the app asks the book for me without my hands leaving the keyboard.
- As a reader, I can see my question appear as a user bubble immediately so that I know the app heard me.
- As a reader, I can see a thinking indicator while the backend works so that I know it's still alive.
- As a reader, I can read the assistant's answer with cited quotes so that I trust the response and can verify it.
- As a reader, I can see "safe through ch. {n}" update as I navigate chapters so that I understand why an answer is scoped the way it is.

## Acceptance criteria

1. The right-column empty state (slice 3's "Chat coming soon" placeholder) is removed and replaced with a centered welcoming empty state reading "Ask about what you've read" when no messages have been sent yet.
2. The disabled textarea in the right-column footer is replaced with a live `ChatInput` (ported from `components2.jsx`). Its placeholder reads `"Ask about what you've read…"`. Typing updates local state; the send button enables only when the trimmed value is non-empty.
3. Pressing Enter (without Shift) in `ChatInput` submits; Shift+Enter inserts a newline. Clicking the send icon submits. Both paths call the same handler.
4. On submit: a new `UserBubble` rendering the question appears immediately in the chat transcript, the input clears, and a request fires to `POST /books/{bookId}/query` with JSON body `{question, search_type: "GRAPH_COMPLETION", max_chapter: <book.current_chapter>}`. The request is awaited; during flight, a placeholder thinking row (e.g. an `AssistantBubble` containing three animated dots or the word "Thinking…") is visible.
5. On 2xx response: the thinking row is replaced by an `AssistantBubble` rendering the assembled answer text (joined from `response.results[].content`) and, if any `results` include non-null `chapter` and text, rendering each as a `Source` entry below the bubble (using the bubble's existing `sources` slot — see Data contracts). Each source shows the result `content` (truncated to ~200 chars) and "Ch. {chapter}" label.
6. If `response.results` is empty, the assistant bubble renders a fallback line: "I don't have anything in your read-so-far that answers that. Try rephrasing, or read further." (No `sources` rendered.)
7. On `fetch` rejection (network failure) or 5xx: the thinking row is replaced by a one-line system-style assistant bubble reading "Something went wrong. Try again." with no sources.
8. On 429: the same row renders "Too many requests, slow down." with no sources.
9. The `max_chapter` value attached to the request equals `book.current_chapter` from the `GET /books` payload the screen already loads. Verifiable via devtools Network tab: submitting a question on `/books/:bookId/read/3` when `current_chapter == 3` sends a body containing `"max_chapter": 3`.
10. The spoiler-safe pill in the right-column header continues to read `"safe through ch. {current_chapter}"` and its value matches the `max_chapter` sent with the most recent query (no drift between pill and wire).
11. Chat history is preserved as the reader navigates within the same mount of `ReadingScreen` (clicking sidebar rows does NOT clear state because the screen does not unmount). Reloading the page OR navigating to Library and back clears history — no persistence.
12. The transcript area scrolls its latest message into view after each submit and after each response. Older messages remain accessible by scrolling up.
13. `curl -X POST http://localhost:8000/books/christmas_carol_e6ddcd76/query -H 'Content-Type: application/json' -d '{"question":"Who is Marley?","search_type":"GRAPH_COMPLETION","max_chapter":1}'` returns 200 with a JSON body matching the `QueryResponse` contract; `result_count` may be 0 and `results` may be `[]` — both are acceptable and the UI handles them per AC 6.
14. `pytest -v` and `npm run test` pass. No slice-1/2/3 tests regress. The Reading screen still satisfies slice-3 acceptance criteria 1–12.

## UI scope

**NEW — port from `design-handoff/project/components2.jsx` to `frontend/src/components/`:**

- `UserBubble` — right-aligned bubble with optional `pageAt` footer (omit the prop for now).
- `AssistantBubble` — left-aligned bubble with avatar disc, optional `sources[]` list, optional `streaming` cursor (unused this slice unless the planner opts into the client-side typewriter polish — see Out of scope).
- `ChatInput` — textarea + send-button composite.

**REUSED — no changes:** `NavBar`, `ChapterRow`, `ProgressPill`, `LockState`, `ProgressiveBlur`, `Row`, `Button`, `IconBtn`, `Wordmark`, `IcChat`, `lib/api.ts` (extended with a new `queryBook` function).

**Replaced in `frontend/src/screens/ReadingScreen.tsx`:** the right-column body placeholder and disabled `<textarea>` footer from slice 3 are replaced with a live chat panel: empty-state → transcript list → live `ChatInput`. The header row (Margin notes label + spoiler-safe pill) is unchanged.

No router changes. No new screens.

## Backend scope

**Existing endpoint reused:** `POST /books/{book_id}/query` in `main.py`.

Current shape (from `main.py`):

- Request (`QueryRequest`): `{ question: str (max_length=2000), search_type: str = "GRAPH_COMPLETION" }`.
- Response (`QueryResponse`): `{ book_id: str, question: str, search_type: str, current_chapter: int, results: QueryResultItem[], result_count: int }`.
- `QueryResultItem`: `{ content: str, entity_type: str | null, chapter: int | null }`.

**Small addition this slice:** add an optional `max_chapter: int | None = None` field to `QueryRequest`. When present and `>= 1`, the endpoint uses it (clamped at the disk value of `current_chapter` so the client cannot raise the ceiling) as the spoiler filter in both the Cognee path and the on-disk fallback path; when absent, behavior is unchanged (reads from `reading_progress.json`). This is purely additive and does not break slice-3 uses.

No new endpoints. No SSE. CORS unchanged. No new env vars.

## Data contracts

```ts
// POST /books/{book_id}/query request
interface QueryRequest {
  question: string;           // 1..2000 chars, trimmed non-empty
  search_type: 'GRAPH_COMPLETION' | 'CHUNKS' | 'SUMMARIES' | 'RAG_COMPLETION';
  max_chapter: number;        // >= 1, == book.current_chapter
}

// POST /books/{book_id}/query response
interface QueryResponse {
  book_id: string;
  question: string;
  search_type: string;
  current_chapter: number;    // effective chapter the backend filtered on
  results: QueryResult[];
  result_count: number;
}

interface QueryResult {
  content: string;
  entity_type: string | null;
  chapter: number | null;
}

// Chat transcript — React state only; never persisted
interface ChatMessage {
  id: string;                                       // crypto.randomUUID()
  role: 'user' | 'assistant';
  status: 'pending' | 'ok' | 'error';
  text: string;                                     // user question OR assembled assistant answer OR error line
  sources?: Source[];                               // assistant-only
  max_chapter_at_send?: number;                     // for debugging / pill assertion
}

interface Source {
  text: string;                                     // from QueryResult.content, truncated for display
  chapter: number;                                  // from QueryResult.chapter (non-null only)
}
```

## Out of scope

- SSE / true token streaming. Planner MAY implement a ~300ms client-side typewriter reveal using `AssistantBubble`'s existing `streaming` cursor if visually nicer, but the default is single-paint render.
- Persisting chat history to disk, `localStorage`, or the backend.
- Margin-note records, per-message "asked at p. X" footers that reflect actual page positions (the `UserBubble.pageAt` prop exists but is not wired).
- Entity-click-through from `Highlight` spans in the reading body.
- Text-selection-to-question affordance ("ask about this passage").
- Suggested-question chips beneath the input (shown in `screens.jsx` mock; defer).
- Multiple chat threads, thread switching, history search, editing past messages.
- Mobile / tablet layouts.
- Regenerating, copying, or rating responses.

## Open questions

- **Does slice-4 ship a backend change or purely consume the existing shape?** Proposed default: ship the additive `max_chapter: int | None = None` on `QueryRequest` so the frontend controls the ceiling. Keep it optional and backward-compatible. Clamp to disk `current_chapter` on the server.
- **Typewriter reveal?** Proposed default: **no** — render the assistant response in a single paint. Planner may opt into a 300ms reveal if trivial (reuses `AssistantBubble streaming`).
- **Empty-state copy.** Proposed default: **"Ask about what you've read"** in `var(--ink-3)` sans-serif, centered vertically in the transcript area.
- **Thinking-state UI.** Proposed default: an `AssistantBubble` rendering the word "Thinking…" with `streaming` cursor; replaced on response.
- **What counts as a "source"?** Proposed default: every `QueryResult` where `chapter != null` is rendered as a source. If all results have `chapter == null`, the assistant bubble renders with no sources.
- **What if `result_count > 10`?** Proposed default: render the top 5 sources; no pagination. Answer text joins all results with `\n\n`.
- **Source text truncation.** Proposed default: 200 chars + ellipsis, preserving the existing italic serif style in `AssistantBubble`.
