# Slice 4 — Frontend Refactor + Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans`. TDD-first where a test is available; otherwise an explicit manual-verification script. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Land the seven audit fixes from the Slice 4 spec — no behavior changes, `ReadingScreen.tsx` < 300 LOC, lint-clean, all tests green.

**Architecture:** Three extracted hooks under `frontend/src/screens/reading/`, four new sub-components (`ReadingHeader`, `ChapterPane`, `AnnotationSidePanel`, `ChatPanel`), one shared `ConnectionBanner`, a `fetchWithTimeout` helper + `NetworkError`, and three CSS migrations. ESLint/Prettier + `.env.example` land first.

**Tech Stack:** React 18, TypeScript 5 (strict), Vite 5, Vitest 2, Playwright 1.59, `@testing-library/react` 16.

**Spec:** `docs/superpowers/specs/2026-04-22-slice-4-frontend-hardening.md`

---

## File structure

**New files:**
- `frontend/.eslintrc.cjs`, `frontend/.prettierrc.json`, `frontend/.env.example`
- `frontend/src/styles/a11y.css`
- `frontend/src/components/ConnectionBanner.tsx` + `.test.tsx`
- `frontend/src/components/ChatInput.css`
- `frontend/src/screens/reading/useReadingState.ts` + `.test.tsx`
- `frontend/src/screens/reading/useChatState.ts` + `.test.tsx`
- `frontend/src/screens/reading/useAnnotations.ts` + `.test.tsx`
- `frontend/src/screens/reading/ReadingHeader.tsx`
- `frontend/src/screens/reading/ChapterPane.tsx`
- `frontend/src/screens/reading/AnnotationSidePanel.tsx`
- `frontend/src/screens/reading/ChatPanel.tsx`

**Modified files:**
- `frontend/package.json`, `frontend/src/lib/api.ts`, `frontend/src/lib/api.test.ts`
- `frontend/src/screens/ReadingScreen.tsx`, `frontend/src/screens/UploadScreen.tsx`, `frontend/src/screens/UploadScreen.test.tsx`
- `frontend/src/components/SelectionToolbar.tsx`, `frontend/src/components/ChatInput.tsx`
- `frontend/src/styles/annotations.css`, `frontend/src/main.tsx`

---

## Embedded subagent briefs

### Test subagent
Write Vitest tests before implementation. Use existing `ReadingScreen.test.tsx` (618 LOC) as behavioral contract: if its assertions still pass after T7/T8/T9/T10, the refactor preserved behavior. New hook-level tests use `renderHook` from `@testing-library/react` v16. **Playwright specs must continue passing without modification** — they're the behavioral backstop.

### Generate subagent
Hard rules:
(a) TypeScript strict stays on.
(b) No new `any` types (`@typescript-eslint/no-explicit-any` enforced).
(c) Hooks receive dependencies as args (inject `queryBook`, `fetchBooks`, etc. — don't import API client directly).
(d) CSS goes to existing files where possible; `a11y.css` is the one new CSS file.
(e) `git mv` for sub-component extractions.
(f) After every task: `npm run lint`, `npm test`, `npm run build`. No red steps — fix before moving on.

### Review subagent
**Spec reviewer:** `ReadingScreen.tsx` < 300 LOC (`wc -l`). All seven in-scope items landed (grep for `fetchWithTimeout`, `VITE_API_BASE_URL`, `.selection-toolbar`, `.chat-input`, `ConnectionBanner`, `:focus-visible`, `screens/reading/useReadingState.ts`). `npm run lint` exits 0.

**Code-quality reviewer:** Hook top-level return shapes ≤ 10 keys (group sub-objects if larger). No duplicated CSS. kebab-case classnames. Focus rings visible in Playwright screenshots. No silent snapshot regenerations. No new `any` types.

---

## Task 1 — Add ESLint + Prettier configs (foundation)

- [ ] `npm i -D eslint @typescript-eslint/parser @typescript-eslint/eslint-plugin eslint-plugin-react eslint-plugin-react-hooks prettier`.
- [ ] Create `.eslintrc.cjs`:
```js
module.exports = {
  root: true,
  parser: "@typescript-eslint/parser",
  parserOptions: { project: "./tsconfig.json", ecmaVersion: 2022, sourceType: "module" },
  plugins: ["@typescript-eslint", "react", "react-hooks"],
  extends: [
    "eslint:recommended",
    "plugin:@typescript-eslint/recommended",
    "plugin:react/recommended",
    "plugin:react/jsx-runtime",
    "plugin:react-hooks/recommended",
  ],
  settings: { react: { version: "detect" } },
  rules: {
    "@typescript-eslint/no-unused-vars": ["error", { argsIgnorePattern: "^_" }],
    "@typescript-eslint/no-explicit-any": "error",
  },
  ignorePatterns: ["dist/", "node_modules/", "e2e/"],
};
```
- [ ] Create `.prettierrc.json`: `{ "semi": true, "singleQuote": false, "trailingComma": "all", "printWidth": 88, "tabWidth": 2 }`.
- [ ] `package.json`: add `"lint": "eslint 'src/**/*.{ts,tsx}' --max-warnings 0"`, `"format:check": "prettier --check 'src/**/*.{ts,tsx,css,json}'"`.
- [ ] Run `npm run lint` once. Fix or annotate each finding.
- [ ] Verify `lint`, `format:check`, `build` all exit 0.
- [ ] **Commit:** "Slice 4 T1: add ESLint + Prettier; lint-clean baseline."

---

## Task 2 — Add `fetchWithTimeout` helper

- [ ] **Red** in `api.test.ts`:
```ts
describe("fetchWithTimeout", () => {
  it("aborts and throws NetworkError after timeoutMs", async () => {
    const neverResolves = new Promise<Response>(() => {});
    vi.stubGlobal("fetch", vi.fn(() => neverResolves));
    vi.useFakeTimers();
    const p = fetchWithTimeout("http://x/y", {}, 100);
    vi.advanceTimersByTime(101);
    await expect(p).rejects.toBeInstanceOf(NetworkError);
    vi.useRealTimers();
  });
});
```
- [ ] `npm test -- api` → red.
- [ ] Add `NetworkError` class + `fetchWithTimeout` to `api.ts`:

```ts
export class NetworkError extends Error {
  constructor(message = "Request timed out") {
    super(message);
    this.name = "NetworkError";
  }
}

export async function fetchWithTimeout(
  url: string,
  init: RequestInit = {},
  timeoutMs = 30_000,
): Promise<Response> {
  const controller = new AbortController();
  const id = setTimeout(() => controller.abort(), timeoutMs);
  try {
    return await fetch(url, { ...init, signal: controller.signal });
  } catch (err) {
    if (err instanceof Error && err.name === "AbortError") {
      throw new NetworkError(`Request to ${url} timed out after ${timeoutMs}ms`);
    }
    throw err;
  } finally {
    clearTimeout(id);
  }
}
```

- [ ] Route every `fetch(` call in `lib/api.ts` through `fetchWithTimeout`. `uploadBook` gets 120s override; 30s default elsewhere.
- [ ] Inside `queryBook`, wrap `NetworkError` as `QueryNetworkError` to preserve the existing error-class discriminator.
- [ ] `npm test -- api` → green. `npm run lint` → green.
- [ ] **Commit:** "Slice 4 T2: fetchWithTimeout + NetworkError; default 30s, upload 120s."

---

## Task 3 — Configurable `BASE_URL`

- [ ] **Red** test:
```ts
it("uses VITE_API_BASE_URL when set", async () => {
  vi.stubEnv("VITE_API_BASE_URL", "https://api.example.com");
  vi.resetModules();
  const freshApi = await import("./api");
  const fetchSpy = vi.spyOn(globalThis, "fetch")
    .mockResolvedValue(new Response(JSON.stringify([]), { status: 200 }));
  await freshApi.fetchBooks();
  expect(fetchSpy).toHaveBeenCalledWith("https://api.example.com/books", expect.anything());
  vi.unstubAllEnvs();
});
```
- [ ] Replace hardcoded `BASE_URL`:
```ts
const BASE_URL =
  (import.meta.env.VITE_API_BASE_URL as string | undefined) ??
  "http://localhost:8000";
```
- [ ] Create `frontend/.env.example`:
```
# BookRAG API base URL. Defaults to http://localhost:8000 if unset.
VITE_API_BASE_URL=http://localhost:8000
```
- [ ] Verify `frontend/.gitignore` excludes `.env` / `.env.local`.
- [ ] Manual: `VITE_API_BASE_URL=http://127.0.0.1:9999 npm run dev`, confirm Network tab hits port 9999.
- [ ] **Commit:** "Slice 4 T3: configurable VITE_API_BASE_URL with .env.example."

---

## Task 4 — Focus rings

- [ ] Create `frontend/src/styles/a11y.css`:
```css
.br :focus-visible {
  outline: 2px solid var(--accent);
  outline-offset: 2px;
  border-radius: var(--r-sm);
}
.br textarea:focus-visible,
.br input:focus-visible {
  outline: 2px solid var(--accent);
  outline-offset: 1px;
}
@media (prefers-reduced-motion: reduce) {
  .br :focus-visible { transition: none; }
}
```
- [ ] Import in `main.tsx` after `tokens.css`, before `annotations.css`.
- [ ] `grep -n 'outline: ?"?none"?' frontend/src -r` — confirm every match has an equivalent ring via `:focus-within` (from T6).
- [ ] **Manual keyboard walkthrough** (script):
  1. `npm run dev`, Chrome.
  2. Tab from initial load → NavBar Library → Upload link (ring visible each stop).
  3. Tab into dropzone button.
  4. Navigate to reading screen. Tab sidebar chapter list → prev/next buttons → chat input container (`:focus-within` ring).
  5. Click somewhere with mouse → confirm no outline on clicked element.
- [ ] `npm run lint && npm test && npm run build` → green.
- [ ] **Commit:** "Slice 4 T4: global :focus-visible a11y ring."

---

## Task 5 — Fix silent polling catches + ConnectionBanner

- [ ] **Red** test in `UploadScreen.test.tsx`:
```ts
it("surfaces a connection banner after 3 consecutive status-poll failures", async () => {
  vi.useFakeTimers();
  const rejects = vi.fn().mockRejectedValue(new Error("network"));
  vi.spyOn(api, "fetchStatus").mockImplementation(rejects);
  vi.spyOn(api, "uploadBook").mockResolvedValue({ book_id: "x", message: "ok" });
  render(<UploadScreen />);
  // drive upload → tracking phase
  for (let i = 0; i < 3; i++) { await vi.advanceTimersByTimeAsync(2000); }
  expect(await screen.findByRole("alert", { name: /connection lost/i })).toBeInTheDocument();
  rejects.mockResolvedValueOnce({} as api.PipelineState);
  await vi.advanceTimersByTimeAsync(2000);
  expect(screen.queryByRole("alert", { name: /connection lost/i })).not.toBeInTheDocument();
  vi.useRealTimers();
});
```
- [ ] Create `ConnectionBanner.tsx`:
```tsx
export function ConnectionBanner({ visible }: { visible: boolean }) {
  if (!visible) return null;
  return (
    <div role="alert" aria-label="Connection lost" className="connection-banner">
      Connection lost. Retrying…
    </div>
  );
}
```
- [ ] Add `.connection-banner` styling to `annotations.css`.
- [ ] Rewrite `UploadScreen.tsx` polling:
```ts
const failures = useRef(0);
const [connectionLost, setConnectionLost] = useState(false);
// .then: failures.current = 0; setConnectionLost(false);
// .catch(err):
//   console.error("pipeline status poll failed", err);
//   failures.current += 1;
//   if (failures.current >= 3) setConnectionLost(true);
```
- [ ] For `ReadingScreen.tsx:93` sidebar fetch (one-shot, not polling): demote to `console.error` only — no banner. **Note the asymmetry in the commit message.**
- [ ] `npm run lint && npm test && npm run build` → green.
- [ ] **Commit:** "Slice 4 T5: ConnectionBanner after 3 consecutive poll failures."

---

## Task 6 — Migrate three inline-style offenders to CSS

- [ ] Add to `annotations.css`:
```css
.selection-toolbar {
  position: fixed;
  transform: translate(-50%, -100%) translateY(-10px);
  background: var(--paper-00);
  border: 1px solid var(--paper-2);
  border-radius: var(--r-lg);
  box-shadow: 0 10px 28px rgba(32,28,22,0.14), 0 1px 3px rgba(0,0,0,0.04);
  padding: 4px;
  display: inline-flex;
  gap: 2px;
  z-index: 20;
  font-family: var(--sans);
  animation: annot-fadeUp 140ms var(--ease-out);
}
.selection-toolbar-btn { /* ... */ }
.selection-toolbar-btn:hover { background: var(--paper-1); }
.reading-cutoff-pill-row { display: flex; justify-content: center; margin-top: 40px; }
```
- [ ] Rewrite `SelectionToolbar.tsx` to use `className="selection-toolbar"`; keep only `style={{ top, left }}` inline (viewport-derived coords).
- [ ] Create `components/ChatInput.css` with `.chat-input` + `:focus-within` rules.
- [ ] Rewrite `ChatInput.tsx` — drop `focus` `useState`, replace inline `<div style={...}>` with `<div className="chat-input">`.
- [ ] Replace `ReadingScreen.tsx` cutoff-pill wrapper with `<div className="reading-cutoff-pill-row">`.
- [ ] **Visual regression sanity (manual):** Playwright screenshot before + after at 1280×800. Diff ≤ 1%.
- [ ] Existing `ChatInput.test.tsx` passes unchanged.
- [ ] `npm run lint && npm test && npm run build` → green.
- [ ] **Commit:** "Slice 4 T6: migrate SelectionToolbar + ChatInput + cutoff-pill wrapper to CSS."

---

## Task 7 — Extract `useReadingState`

- [ ] **Red** hook test using `renderHook`:
```tsx
const wrapper = ({ children }) => (
  <MemoryRouter initialEntries={["/books/b1/read/2"]}>
    <Routes><Route path="/books/:bookId/read/:chapterNum" element={children} /></Routes>
  </MemoryRouter>
);
it("loads book + chapters on mount", async () => {
  const fetchBooks = vi.fn().mockResolvedValue([BOOK_FIXTURE]);
  const fetchChapters = vi.fn().mockResolvedValue(CHAPTERS_FIXTURE);
  const fetchChapter = vi.fn().mockResolvedValue(CHAPTER_2_FIXTURE);
  const { result } = renderHook(() => useReadingState({
    fetchBooks, fetchChapters, fetchChapter, setProgress: vi.fn()
  }), { wrapper });
  await waitFor(() => expect(result.current.book).not.toBeNull());
  expect(result.current.chapterList).toHaveLength(3);
  expect(result.current.body.kind).toBe("ok");
});
```
- [ ] Create `useReadingState.ts`. All deps injected as args for testability.
- [ ] In `ReadingScreen.tsx`, replace book/chapter/body effects with `const { book, chapterList, body, handleMarkAsRead } = useReadingState(...)`.
- [ ] `npm test -- ReadingScreen` — existing screen test passes unchanged.
- [ ] `npm test -- useReadingState` — new hook test green.
- [ ] **Commit:** "Slice 4 T7: extract useReadingState."

---

## Task 8 — Extract `useChatState`

- [ ] **Red** hook test covering: submit, thinking→ok bubble, rate-limit path, network-error path, pendingQuery clear after submit.
- [ ] Create `useChatState.ts`. Accepts `{ book, bookId, queryBook, onAnswered? }`. `onAnswered` lets annotations clear cutoff after query — avoids the hook importing annotations.
- [ ] Replace chat block in `ReadingScreen.tsx`.
- [ ] Existing `ReadingScreen.test.tsx` covers chat integration — still passes.
- [ ] **Commit:** "Slice 4 T8: extract useChatState."

---

## Task 9 — Extract `useAnnotations`

- [ ] **Red** hook test covering: seed+user merge, per-chapter filter, `mouseup` with stubbed `window.getSelection`, `onSelectionAction("ask")` creates query annotation + cutoff + pendingQuery, `saveNote` persists, `Escape` clears cutoff.
- [ ] Create `useAnnotations.ts`. Group sub-state: `selection: { state, noteDraft, pendingQuery, onAction, saveNote, setPendingQuery }` to keep top-level return shape ≤ 10 keys.
- [ ] Remove all corresponding state + effects from `ReadingScreen.tsx`.
- [ ] Wire `useChatState.onAnswered = annotations.clearCurrentCutoff`.
- [ ] **Commit:** "Slice 4 T9: extract useAnnotations."

---

## Task 10 — Compose ReadingScreen + sub-components

- [ ] Create `ReadingHeader.tsx` (left sidebar), `ChapterPane.tsx` (center), `AnnotationSidePanel.tsx` (right), `ChatPanel.tsx` (thread-tab content).
- [ ] Rewrite `ReadingScreen.tsx` as orchestration:
```tsx
export function ReadingScreen() {
  const { bookId = "", chapterNum = "1" } = useParams<...>();
  const n = Number.parseInt(chapterNum, 10) || 1;
  const reading = useReadingState({ fetchBooks, fetchChapters, fetchChapter, setProgress, bookId, n });
  const annotations = useAnnotations({ bookId, n });
  const chat = useChatState({
    bookId, book: reading.book, queryBook,
    pendingQuery: annotations.selection.pendingQuery,
    onAnswered: annotations.clearCurrentCutoff,
  });
  return (
    <div className="br reading-layout">
      <NavBar />
      <div className="reading-grid" data-panel-open={annotations.panelOpen}>
        <ReadingHeader {...} />
        <ChapterPane {...} />
        <AnnotationSidePanel {...} thread={<ChatPanel {...} />} />
      </div>
      {annotations.selection.state && <SelectionToolbar {...} />}
      {annotations.selection.noteDraft && <NoteComposer {...} />}
    </div>
  );
}
```
- [ ] Move grid-template-columns to `.reading-grid` + `.reading-grid[data-panel-open="true"]` in `annotations.css`.
- [ ] `wc -l ReadingScreen.tsx` → **< 300**.
- [ ] `npm run lint && npm test && npm run build` → green.
- [ ] **Commit:** "Slice 4 T10: compose ReadingScreen < 300 LOC from hooks + sub-components."

---

## Task 11 — Full test run + Playwright sweep

- [ ] `npm run lint` → 0.
- [ ] `npm run format:check` → 0.
- [ ] `npm test` → 0.
- [ ] `npm run build` → 0.
- [ ] `npm run test:e2e` → all three specs green (`chat.spec.ts`, `reading.spec.ts`, `upload.spec.ts`).
- [ ] Manual keyboard walkthrough from spec metric #6.
- [ ] `wc -l ReadingScreen.tsx` — print the number.

---

## Task 12 — Final commit + cleanup

- [ ] Review branch: `git log --oneline main..HEAD` → ~10 commits (T1–T10).
- [ ] `.env.example` committed, `.env` untracked.
- [ ] No new `any`: `grep -n ': any\b' frontend/src -r` returns nothing.
- [ ] Push branch, open PR titled "Slice 4: frontend refactor + hardening".

## Critical Files

- /Users/jeffreykrapf/Documents/thefinalbookrag/frontend/src/screens/ReadingScreen.tsx
- /Users/jeffreykrapf/Documents/thefinalbookrag/frontend/src/lib/api.ts
- /Users/jeffreykrapf/Documents/thefinalbookrag/frontend/src/screens/UploadScreen.tsx
- /Users/jeffreykrapf/Documents/thefinalbookrag/frontend/src/styles/annotations.css
- /Users/jeffreykrapf/Documents/thefinalbookrag/frontend/package.json
