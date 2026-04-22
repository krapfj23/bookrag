# Slice 4 — Frontend Refactor + Hardening PRD

**Date:** 2026-04-22
**Parent:** Frontend audit follow-up (maintenance slice, no user-facing features)
**Depends on:** Nothing blocking; runs against current `main`.

## Goal

Shrink `ReadingScreen.tsx` from 907 LOC to under 300 by extracting three hooks, and close seven audit-surfaced quality gaps (silent polling catches, missing lint/format, inline styles, hardcoded BASE_URL, invisible focus rings, fetch timeouts) — all without shipping new features or re-architecting state.

## Architecture — new `ReadingScreen`

```
ReadingScreen (orchestrator, <300 LOC)
│
├── useReadingState({ bookId, chapterNum })
│     fetches Book + ChapterSummary[] + Chapter, exposes:
│       { book, chapterList, body, mark, navigation }
│     owns polling + silent-catch fix (banner via onConnectionLost cb)
│
├── useChatState({ book, bookId, queryBook })
│     owns messages, draft, submit, pendingQuery chip:
│       { messages, draft, setDraft, submit, pendingQuery, setPendingQuery }
│     receives queryBook by injection (testability)
│
├── useAnnotations({ bookId, chapterNum })
│     owns notes/highlights/cutoffs + selection handling:
│       { chapterAnnotations, notes, highlights, cutoff,
│         selection, peek, onSelectionAction, saveNote, clearCutoff,
│         panelOpen, panelTab, focusedAnnotationId, ... }
│
└── composition:
    <ReadingHeader title progressPill chapterList onNavigate />
    <ChapterPane body cutoff chapterAnnotations peek onPeek readerRef />
    <ChatPanel messages draft onSubmit pendingQuery onClearPending />
    <AnnotationSidePanel tab onTabChange notes highlights thread={ChatPanel} />
    <SelectionToolbar selection onAction />
    <NoteComposer noteDraft onSave onCancel />

Side-channels:
  useChatState.submit() calls useAnnotations.clearCutoff() after resolution
  → implemented as an optional `onAnswered` callback injected at composition time.
```

Hook size budget: each hook's return value ≤ 10 keys. If it grows past 10, split.

## In-scope items

### 1. Split `ReadingScreen.tsx` (907 LOC)

**Problem.** A single file owns seven concerns: book/chapter fetch, chapter navigation, chat messages, query submission, annotation persistence, selection-to-annotation flow, and spoiler cutoff.

**Fix.** Extract three hooks into `frontend/src/screens/reading/`:
- `useReadingState.ts` — `book`, `chapterList`, `body` (idle|loading|error|ok), navigation helpers, `handleMarkAsRead`, silent-poll fix.
- `useChatState.ts` — `messages`, `draft`, `submit`, `submitting`, `pendingQuery`. Receives `queryBook` as an argument.
- `useAnnotations.ts` — merged annotations, `chapterAnnotations`, `cutoff`, `peek`, `panelOpen`, `panelTab`, `focusedAnnotationId`, `selection`, `noteDraft`, `onSelectionAction`, `saveNote`, `clearCurrentCutoff`, document-level `mouseup` + `Escape` effects.

`ReadingScreen.tsx` becomes an orchestrator composing four new sub-components: `<ReadingHeader>`, `<ChapterPane>`, `<AnnotationSidePanel>`, `<ChatPanel>`. Target: < 300 LOC.

**Why this fix.** Hooks carve concerns along seams that already exist in the code (the current file has section comments like `// ── Chat state ──`). Each hook is independently renderHook-testable.

### 2. Fix silent polling `.catch` blocks

**Problem.** `ReadingScreen.tsx:93` (sidebar book/chapter fetch) and `UploadScreen.tsx:139` (pipeline status poll) swallow errors silently.

**Fix.** Replace each with:
1. `console.error("<context>", err)` — always logged.
2. Bump a `consecutiveFailures` ref.
3. Once `consecutiveFailures >= 3`, surface an inline `ConnectionBanner` ("Connection lost. Retrying…").
4. Next successful poll resets counter and dismisses banner.

New `components/ConnectionBanner.tsx` as a reusable primitive.

### 3. Add ESLint + Prettier

**Problem.** No lint or format config in `frontend/`.

**Fix.** Add `.eslintrc.cjs` with `eslint:recommended`, `@typescript-eslint/recommended`, `plugin:react-hooks/recommended`, `plugin:react/recommended + jsx-runtime`. Add `.prettierrc.json` with conservative defaults matching the existing codebase. Add npm scripts `lint` and `format:check`. Max-warnings 0.

### 4. Migrate three flagged inline-style offenders to CSS

**Problem.** ~45 components use inline styles despite the comprehensive `tokens.css`.

**Fix.** Migrate only the three worst offenders:
- `SelectionToolbar.tsx` → `.selection-toolbar` class in `annotations.css`
- `ChatInput.tsx` → `.chat-input` class with `:focus-within` border/shadow; drop the `focus` `useState`
- Reading-cutoff-pill wrapper → `.reading-cutoff-pill-row` class

Subsequent slices can follow through on the other 42.

### 5. Configurable `BASE_URL`

**Problem.** `frontend/src/lib/api.ts:51` hardcodes `http://localhost:8000`.

**Fix.** `const BASE_URL = (import.meta.env.VITE_API_BASE_URL as string | undefined) ?? "http://localhost:8000";`. Add `.env.example` documenting the variable.

### 6. Focus rings

**Problem.** `ChatInput.tsx:60` sets `outline: "none"` without a visible `:focus-visible` replacement.

**Fix.** Add `frontend/src/styles/a11y.css` with `:focus-visible` rules using the accent token. Import from `main.tsx`. `:focus-visible` only shows keyboard focus, leaves mouse-focus visually unchanged.

### 7. Fetch timeouts

**Problem.** Every `fetch()` in `frontend/src/lib/api.ts` has no timeout.

**Fix.** Add `fetchWithTimeout` helper using `AbortController`, default 30s, `uploadBook` override 120s. New `NetworkError` class. Route all `lib/api.ts` calls through it.

## Non-goals (explicit)

- No new user-facing features.
- No design-token restructure.
- No state library migration (hooks stay).
- No bundler swap, no React upgrade.
- No exhaustive inline-style migration — only the three components in item 4.
- No new README.
- No Python-side changes.

## Success metrics

1. `wc -l frontend/src/screens/ReadingScreen.tsx` < 300.
2. `npm run lint` exits 0 with `--max-warnings 0`.
3. `npm run build` exits 0.
4. `npm test` — all existing Vitest suites pass. New hook tests land green.
5. `npm run test:e2e` — all three Playwright specs pass unchanged (behavioral backstop).
6. **Manual keyboard walkthrough:** tab from `NavBar` → Upload → drop an EPUB → tracking card → Library → open a book → `ChapterRow` → reading column → `ChatInput` → send. Every focusable element shows a visible accent-colored ring.
