# Slice R2 — V3 Inline cards + selection→ask + notes — Implementation Plan

**Date:** 2026-04-22
**Parent spec:** `/Users/jeffreykrapf/Documents/thefinalbookrag/docs/superpowers/specs/2026-04-22-slice-R2-cards-and-selection.md`
**Depends on:** R1 reading surface (sentence anchors, spread paginator, fog-of-war cursor).

## Decisions locked for this plan

- **Ask prompt template (spec open question 1):** `Asked about "{quote}": what does this mean in context?` — short, matches spec's illustrative wording, fits the free-form `question` field the backend already accepts.
- **Fog-of-war on Ask button (spec open question 2):** visibly **disabled** with `title="Reach this sentence first"`; Note/Highlight remain enabled.
- **Notes past cursor (spec open question 3):** allowed (no LLM leakage).
- **Highlight action:** no-op visual per PRD AC 8; clears selection, no storage write.
- **Streaming simulator:** split the final answer on whitespace into 1–3 word chunks, append at a 25–60ms jittered cadence, bail out instantly if component unmounts.
- **On-page indicators:** rendered by extending `Sentence` to accept an optional set of `{ kind: "ask" | "note", cardId }[]` marks (per-sentence lookup built once per render in `BookSpread`). This keeps per-sentence concern local, supports click-to-focus, and composes cleanly with fog styling.
- **Margin column anchor matching:** `MarginColumn` receives `visibleSids: Set<string>` derived from `current.left.paragraphs` + `current.right.paragraphs`. Cards whose `anchor` is in this set render; else suppressed for this spread.
- **Legacy deletions:** `AnnotationRail`, `AnnotationPanel`, `AnnotationPeek`, `NoteComposer`, `AnnotatedParagraph`, `useAnnotations` (+ their test files). `SelectionToolbar.tsx` is **rewritten in place** (not deleted) per the locked-context directive; its CSS classes are replaced with inline/pill styling per handoff §5.

---

## Task breakdown (12 tasks, tests-first)

Each task follows: Goal / Files / Failing test / Run (expect FAIL) / Implementation / Run (expect PASS) / Commit.

---

### T1 · Add `Card` + `CardStore` types and `useCards` hook (localStorage)

**Goal:** Introduce the `Card` discriminated union and a `useCards(bookId)` hook that loads, creates, updates, and persists cards in `localStorage` under `bookrag.cards.{bookId}`.

**Files:**
- Create: `frontend/src/lib/reader/cards.ts` (types + `CARDS_KEY`, `readStoredCards`, `writeStoredCards`)
- Create: `frontend/src/lib/reader/useCards.ts` (React hook)
- Test: `frontend/src/lib/reader/useCards.test.tsx`

**Failing test** (verbatim):

```tsx
import { describe, it, expect, beforeEach } from "vitest";
import { renderHook, act } from "@testing-library/react";
import { useCards, CARDS_KEY } from "./useCards";

describe("useCards", () => {
  beforeEach(() => window.localStorage.clear());

  it("starts empty and persists new ask card to localStorage", () => {
    const { result } = renderHook(() => useCards("book-1"));
    expect(result.current.cards).toEqual([]);
    act(() => {
      result.current.createAsk({
        anchor: "p1.s1",
        quote: "hello",
        chapter: 1,
        question: "what?",
      });
    });
    expect(result.current.cards).toHaveLength(1);
    const raw = window.localStorage.getItem(CARDS_KEY("book-1"));
    expect(raw).not.toBeNull();
    const parsed = JSON.parse(raw!);
    expect(parsed.version).toBe(1);
    expect(parsed.cards[0].kind).toBe("ask");
    expect(parsed.cards[0].quote).toBe("hello");
  });

  it("updateAsk mutates answer field and persists", () => {
    const { result } = renderHook(() => useCards("book-1"));
    let id = "";
    act(() => {
      id = result.current.createAsk({
        anchor: "p1.s1",
        quote: "q",
        chapter: 1,
        question: "Q?",
      });
    });
    act(() => {
      result.current.updateAsk(id, (prev) => ({ ...prev, answer: "A" }));
    });
    const card = result.current.cards.find((c) => c.id === id);
    expect(card && card.kind === "ask" && card.answer).toBe("A");
  });

  it("createNote with empty body is allowed (body committed later)", () => {
    const { result } = renderHook(() => useCards("book-1"));
    act(() => {
      result.current.createNote({ anchor: "p1.s2", quote: "x", chapter: 1 });
    });
    expect(result.current.cards[0].kind).toBe("note");
  });

  it("removeCard deletes by id and persists", () => {
    const { result } = renderHook(() => useCards("book-1"));
    let id = "";
    act(() => {
      id = result.current.createNote({ anchor: "p1.s1", quote: "x", chapter: 1 });
    });
    act(() => result.current.removeCard(id));
    expect(result.current.cards).toEqual([]);
  });

  it("restores from localStorage on mount", () => {
    window.localStorage.setItem(
      CARDS_KEY("book-1"),
      JSON.stringify({
        version: 1,
        cards: [
          {
            id: "abc",
            bookId: "book-1",
            anchor: "p1.s1",
            quote: "q",
            chapter: 1,
            kind: "note",
            body: "hi",
            createdAt: "2026-04-22T00:00:00Z",
            updatedAt: "2026-04-22T00:00:00Z",
          },
        ],
      }),
    );
    const { result } = renderHook(() => useCards("book-1"));
    expect(result.current.cards).toHaveLength(1);
    expect(result.current.cards[0].id).toBe("abc");
  });

  it("isolates cards per bookId", () => {
    const { result: a } = renderHook(() => useCards("a"));
    act(() => a.current.createNote({ anchor: "p1.s1", quote: "x", chapter: 1 }));
    const { result: b } = renderHook(() => useCards("b"));
    expect(b.current.cards).toEqual([]);
  });
});
```

**Run:** `cd frontend && npm test -- --run src/lib/reader/useCards.test.tsx`
Expected FAIL: `Cannot find module './useCards'`.

**Implementation** (verbatim):

`frontend/src/lib/reader/cards.ts`:

```ts
export interface BaseCard {
  id: string;
  bookId: string;
  anchor: string;
  quote: string;
  chapter: number;
  createdAt: string;
  updatedAt: string;
}

export interface AskCard extends BaseCard {
  kind: "ask";
  question: string;
  answer: string;
  followups: { question: string; answer: string }[];
}

export interface NoteCard extends BaseCard {
  kind: "note";
  body: string;
}

export type Card = AskCard | NoteCard;

export interface CardStore {
  version: 1;
  cards: Card[];
}

export const CARDS_KEY = (bookId: string) => `bookrag.cards.${bookId}`;

export function readStoredCards(bookId: string): Card[] {
  try {
    const raw = window.localStorage.getItem(CARDS_KEY(bookId));
    if (!raw) return [];
    const parsed = JSON.parse(raw) as CardStore;
    if (parsed && parsed.version === 1 && Array.isArray(parsed.cards)) {
      return parsed.cards;
    }
    return [];
  } catch {
    return [];
  }
}

export function writeStoredCards(bookId: string, cards: Card[]): void {
  try {
    const store: CardStore = { version: 1, cards };
    window.localStorage.setItem(CARDS_KEY(bookId), JSON.stringify(store));
  } catch {
    /* ignore quota */
  }
}

export function newCardId(): string {
  if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
    return crypto.randomUUID();
  }
  return `c_${Math.random().toString(36).slice(2)}_${Date.now().toString(36)}`;
}
```

`frontend/src/lib/reader/useCards.ts`:

```ts
import { useCallback, useEffect, useRef, useState } from "react";
import {
  CARDS_KEY,
  newCardId,
  readStoredCards,
  writeStoredCards,
  type AskCard,
  type Card,
  type NoteCard,
} from "./cards";

export { CARDS_KEY } from "./cards";
export type { Card, AskCard, NoteCard } from "./cards";

type CreateAskInput = {
  anchor: string;
  quote: string;
  chapter: number;
  question: string;
};

type CreateNoteInput = {
  anchor: string;
  quote: string;
  chapter: number;
};

export function useCards(bookId: string) {
  const [cards, setCards] = useState<Card[]>(() => readStoredCards(bookId));
  // Re-seed when bookId changes.
  const lastBook = useRef(bookId);
  useEffect(() => {
    if (lastBook.current !== bookId) {
      lastBook.current = bookId;
      setCards(readStoredCards(bookId));
    }
  }, [bookId]);

  const commit = useCallback(
    (next: Card[]) => {
      writeStoredCards(bookId, next);
      setCards(next);
    },
    [bookId],
  );

  const createAsk = useCallback(
    (input: CreateAskInput): string => {
      const now = new Date().toISOString();
      const card: AskCard = {
        id: newCardId(),
        bookId,
        anchor: input.anchor,
        quote: input.quote,
        chapter: input.chapter,
        kind: "ask",
        question: input.question,
        answer: "",
        followups: [],
        createdAt: now,
        updatedAt: now,
      };
      commit([...readStoredCards(bookId), card]);
      return card.id;
    },
    [bookId, commit],
  );

  const createNote = useCallback(
    (input: CreateNoteInput): string => {
      const now = new Date().toISOString();
      const card: NoteCard = {
        id: newCardId(),
        bookId,
        anchor: input.anchor,
        quote: input.quote,
        chapter: input.chapter,
        kind: "note",
        body: "",
        createdAt: now,
        updatedAt: now,
      };
      commit([...readStoredCards(bookId), card]);
      return card.id;
    },
    [bookId, commit],
  );

  const updateAsk = useCallback(
    (id: string, updater: (prev: AskCard) => AskCard) => {
      const current = readStoredCards(bookId);
      const next = current.map((c) => {
        if (c.id !== id || c.kind !== "ask") return c;
        const updated = updater(c);
        return { ...updated, updatedAt: new Date().toISOString() };
      });
      commit(next);
    },
    [bookId, commit],
  );

  const updateNote = useCallback(
    (id: string, body: string) => {
      const current = readStoredCards(bookId);
      const next = current.map((c) => {
        if (c.id !== id || c.kind !== "note") return c;
        return { ...c, body, updatedAt: new Date().toISOString() };
      });
      commit(next);
    },
    [bookId, commit],
  );

  const removeCard = useCallback(
    (id: string) => {
      commit(readStoredCards(bookId).filter((c) => c.id !== id));
    },
    [bookId, commit],
  );

  const findByAnchorAndKind = useCallback(
    (anchor: string, kind: Card["kind"]): Card | undefined =>
      cards.find((c) => c.anchor === anchor && c.kind === kind),
    [cards],
  );

  return {
    cards,
    createAsk,
    createNote,
    updateAsk,
    updateNote,
    removeCard,
    findByAnchorAndKind,
  };
}
```

**Run:** `cd frontend && npm test -- --run src/lib/reader/useCards.test.tsx` → all 6 green.

**Commit:**
```
git add frontend/src/lib/reader/cards.ts frontend/src/lib/reader/useCards.ts frontend/src/lib/reader/useCards.test.tsx
git commit -m "Slice R2 T1: add Card types and useCards localStorage hook"
```

---

### T2 · Client-side streaming simulator (`streamInto`)

**Goal:** Pure async utility that walks a full answer string in 1–3 word chunks at 25–60ms jittered cadence, invoking an `onChunk(nextSoFar)` callback, cancelable via AbortSignal.

**Files:**
- Create: `frontend/src/lib/reader/streamSimulator.ts`
- Test: `frontend/src/lib/reader/streamSimulator.test.ts`

**Failing test:**

```ts
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { simulateStream } from "./streamSimulator";

describe("simulateStream", () => {
  beforeEach(() => vi.useFakeTimers());
  afterEach(() => vi.useRealTimers());

  it("appends chunks until the full answer is delivered", async () => {
    const received: string[] = [];
    const promise = simulateStream("alpha beta gamma delta epsilon zeta", {
      onChunk: (s) => received.push(s),
      minMs: 10,
      maxMs: 10,
      minWords: 1,
      maxWords: 1,
    });
    await vi.runAllTimersAsync();
    await promise;
    expect(received[received.length - 1]).toBe(
      "alpha beta gamma delta epsilon zeta",
    );
    expect(received.length).toBeGreaterThan(1);
  });

  it("short-circuits on abort without calling onChunk again", async () => {
    const onChunk = vi.fn();
    const controller = new AbortController();
    const promise = simulateStream("a b c d e f g h i j", {
      onChunk,
      minMs: 10,
      maxMs: 10,
      minWords: 1,
      maxWords: 1,
      signal: controller.signal,
    });
    await vi.advanceTimersByTimeAsync(15);
    const calls = onChunk.mock.calls.length;
    controller.abort();
    await vi.runAllTimersAsync();
    await promise;
    expect(onChunk.mock.calls.length).toBe(calls);
  });

  it("handles empty answer without throwing", async () => {
    const onChunk = vi.fn();
    await simulateStream("", { onChunk, minMs: 1, maxMs: 1 });
    expect(onChunk).toHaveBeenCalledWith("");
  });
});
```

**Run:** FAIL (module missing).

**Implementation** (`frontend/src/lib/reader/streamSimulator.ts`):

```ts
export interface StreamOptions {
  onChunk: (soFar: string) => void;
  minMs?: number;
  maxMs?: number;
  minWords?: number;
  maxWords?: number;
  signal?: AbortSignal;
}

export async function simulateStream(
  full: string,
  opts: StreamOptions,
): Promise<void> {
  const {
    onChunk,
    minMs = 25,
    maxMs = 60,
    minWords = 1,
    maxWords = 3,
    signal,
  } = opts;
  if (!full) {
    onChunk("");
    return;
  }
  // Preserve whitespace by splitting on word-boundaries while keeping separators.
  const tokens = full.match(/\S+\s*/g) ?? [full];
  let idx = 0;
  let soFar = "";
  while (idx < tokens.length) {
    if (signal?.aborted) return;
    const take =
      minWords +
      Math.floor(Math.random() * Math.max(1, maxWords - minWords + 1));
    const slice = tokens.slice(idx, idx + take).join("");
    soFar += slice;
    idx += take;
    onChunk(soFar);
    if (idx >= tokens.length) break;
    const delay =
      minMs + Math.floor(Math.random() * Math.max(1, maxMs - minMs + 1));
    await new Promise<void>((resolve) => {
      const t = setTimeout(resolve, delay);
      signal?.addEventListener("abort", () => {
        clearTimeout(t);
        resolve();
      });
    });
  }
}
```

**Run:** `npm test -- --run src/lib/reader/streamSimulator.test.ts` → 3 green.

**Commit:**
```
git add frontend/src/lib/reader/streamSimulator.ts frontend/src/lib/reader/streamSimulator.test.ts
git commit -m "Slice R2 T2: add client-side streaming simulator"
```

---

### T3 · Selection helpers (`computeSelection`)

**Goal:** Utility that, given a `Selection` range within a container, returns `{ anchorSid, quote, rect } | null`. Uses `range.startContainer` walked up to the nearest `[data-sid]`; rejects empty / collapsed ranges.

**Files:**
- Create: `frontend/src/lib/reader/selection.ts`
- Test: `frontend/src/lib/reader/selection.test.ts`

**Failing test:**

```ts
import { describe, it, expect } from "vitest";
import { computeSelection } from "./selection";

function setupDom(): HTMLElement {
  const root = document.createElement("div");
  root.innerHTML = `
    <p>
      <span data-sid="p1.s1">Alpha sentence.</span>
      <span data-sid="p1.s2">Bravo sentence.</span>
    </p>`;
  document.body.appendChild(root);
  return root;
}

describe("computeSelection", () => {
  it("returns null for collapsed selection", () => {
    const root = setupDom();
    const range = document.createRange();
    const target = root.querySelector('[data-sid="p1.s1"]')!;
    range.setStart(target.firstChild!, 0);
    range.setEnd(target.firstChild!, 0);
    expect(computeSelection(range, root)).toBeNull();
  });

  it("returns anchorSid from range start and exact quote text", () => {
    const root = setupDom();
    const span = root.querySelector('[data-sid="p1.s1"]')!;
    const text = span.firstChild as Text;
    const range = document.createRange();
    range.setStart(text, 0);
    range.setEnd(text, 5); // "Alpha"
    const res = computeSelection(range, root);
    expect(res).not.toBeNull();
    expect(res!.anchorSid).toBe("p1.s1");
    expect(res!.quote).toBe("Alpha");
  });

  it("returns null when range is outside the container", () => {
    const root = setupDom();
    const outside = document.createElement("span");
    document.body.appendChild(outside);
    outside.textContent = "x";
    const range = document.createRange();
    range.setStart(outside.firstChild!, 0);
    range.setEnd(outside.firstChild!, 1);
    expect(computeSelection(range, root)).toBeNull();
  });
});
```

**Run:** FAIL.

**Implementation** (`frontend/src/lib/reader/selection.ts`):

```ts
export interface ComputedSelection {
  anchorSid: string;
  quote: string;
  rect: DOMRect;
}

function findSidAncestor(node: Node | null): string | null {
  let cur: Node | null = node;
  while (cur) {
    if (cur instanceof HTMLElement) {
      const sid = cur.getAttribute("data-sid");
      if (sid) return sid;
    }
    cur = cur.parentNode;
  }
  return null;
}

export function computeSelection(
  range: Range,
  container: HTMLElement,
): ComputedSelection | null {
  if (range.collapsed) return null;
  // Require both endpoints to live inside the container.
  if (
    !container.contains(range.startContainer) ||
    !container.contains(range.endContainer)
  ) {
    return null;
  }
  const anchorSid = findSidAncestor(range.startContainer);
  if (!anchorSid) return null;
  const quote = range.toString().trim();
  if (!quote) return null;
  const rect = range.getBoundingClientRect();
  return { anchorSid, quote, rect };
}
```

**Run:** 3 green.

**Commit:**
```
git add frontend/src/lib/reader/selection.ts frontend/src/lib/reader/selection.test.ts
git commit -m "Slice R2 T3: add computeSelection helper"
```

---

### T4 · Rewrite `SelectionToolbar` (dark pill, 180ms fade+slide)

**Goal:** Replace existing CSS-class-based toolbar with a dark pill (~32px tall) bearing Ask / Note / Highlight buttons per handoff §5. Supports a `disabled: Partial<Record<Action, boolean>>` prop so fog-of-war can disable Ask.

**Files:**
- Modify: `frontend/src/components/SelectionToolbar.tsx`
- Test: `frontend/src/components/SelectionToolbar.test.tsx` (new)

**Failing test:**

```tsx
import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { SelectionToolbar } from "./SelectionToolbar";

describe("SelectionToolbar", () => {
  it("renders Ask, Note, Highlight buttons and fires onAction", async () => {
    const onAction = vi.fn();
    render(
      <SelectionToolbar top={100} left={120} onAction={onAction} disabled={{}} />,
    );
    expect(screen.getByRole("button", { name: /Ask/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Note/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Highlight/i })).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: /Ask/i }));
    expect(onAction).toHaveBeenCalledWith("ask");
  });

  it("disables Ask when disabled.ask is true and does not fire onAction", async () => {
    const onAction = vi.fn();
    render(
      <SelectionToolbar
        top={0}
        left={0}
        onAction={onAction}
        disabled={{ ask: true }}
      />,
    );
    const ask = screen.getByRole("button", { name: /Ask/i });
    expect(ask).toBeDisabled();
    await userEvent.click(ask);
    expect(onAction).not.toHaveBeenCalled();
  });

  it("has role=toolbar positioned via inline top/left", () => {
    render(<SelectionToolbar top={77} left={33} onAction={() => {}} disabled={{}} />);
    const tb = screen.getByRole("toolbar");
    expect(tb.getAttribute("style")).toMatch(/top: 77px/);
    expect(tb.getAttribute("style")).toMatch(/left: 33px/);
  });
});
```

**Run:** FAIL (current component has no `disabled` prop, ambiguous button accessible names).

**Implementation** (replace `frontend/src/components/SelectionToolbar.tsx` in full):

```tsx
import type { CSSProperties } from "react";

export type SelectionAction = "ask" | "note" | "highlight";

interface Props {
  top: number;
  left: number;
  onAction: (action: SelectionAction) => void;
  disabled?: Partial<Record<SelectionAction, boolean>>;
}

const pillStyle: CSSProperties = {
  position: "fixed",
  display: "inline-flex",
  alignItems: "center",
  gap: 2,
  height: 32,
  padding: "0 4px",
  borderRadius: 999,
  background: "var(--ink-0)",
  color: "var(--paper-00)",
  boxShadow: "0 4px 16px -4px rgba(28,24,18,.35)",
  fontFamily: "var(--sans)",
  fontSize: 12,
  letterSpacing: 0.2,
  zIndex: 50,
  transform: "translate(-50%, -100%) translateY(-6px)",
  opacity: 1,
  transition: "opacity 180ms ease, transform 180ms ease",
  userSelect: "none",
};

const btnStyle = (disabled: boolean): CSSProperties => ({
  height: 26,
  padding: "0 10px",
  borderRadius: 999,
  background: "transparent",
  color: disabled ? "color-mix(in oklab, var(--paper-00) 45%, transparent)" : "var(--paper-00)",
  border: 0,
  cursor: disabled ? "not-allowed" : "pointer",
  fontFamily: "var(--sans)",
  fontSize: 12,
});

export function SelectionToolbar({ top, left, onAction, disabled = {} }: Props) {
  const askDisabled = !!disabled.ask;
  const noteDisabled = !!disabled.note;
  const hlDisabled = !!disabled.highlight;
  return (
    <div
      role="toolbar"
      aria-label="Selection actions"
      data-testid="selection-toolbar"
      style={{ ...pillStyle, top, left }}
      onMouseDown={(e) => e.preventDefault()}
    >
      <button
        type="button"
        aria-label="Ask"
        disabled={askDisabled}
        title={askDisabled ? "Reach this sentence first" : "Ask a question"}
        onClick={() => !askDisabled && onAction("ask")}
        style={btnStyle(askDisabled)}
      >
        Ask
      </button>
      <button
        type="button"
        aria-label="Note"
        disabled={noteDisabled}
        title="Add a note"
        onClick={() => !noteDisabled && onAction("note")}
        style={btnStyle(noteDisabled)}
      >
        Note
      </button>
      <button
        type="button"
        aria-label="Highlight"
        disabled={hlDisabled}
        title="Highlight passage"
        onClick={() => !hlDisabled && onAction("highlight")}
        style={btnStyle(hlDisabled)}
      >
        Highlight
      </button>
    </div>
  );
}
```

**Run:** 3 green.

**Commit:**
```
git add frontend/src/components/SelectionToolbar.tsx frontend/src/components/SelectionToolbar.test.tsx
git commit -m "Slice R2 T4: rewrite SelectionToolbar as dark pill per V3 handoff"
```

---

### T5 · `AskCard`, `NoteCard`, `S1EmptyCard`, `MarginColumn`

**Goal:** Render V3 Inline margin cards per handoff §1 (paper bg, 3px accent border-left, 10px radius, subtle rotation). `MarginColumn` filters cards by `visibleSids`, renders `S1EmptyCard` when empty.

**Files:**
- Create: `frontend/src/components/reader/AskCard.tsx`
- Create: `frontend/src/components/reader/NoteCard.tsx`
- Create: `frontend/src/components/reader/S1EmptyCard.tsx`
- Create: `frontend/src/components/reader/MarginColumn.tsx`
- Test: `frontend/src/components/reader/MarginColumn.test.tsx`

**Failing test:**

```tsx
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { MarginColumn } from "./MarginColumn";
import type { Card } from "../../lib/reader/cards";

const ask: Card = {
  id: "a1",
  bookId: "b",
  anchor: "p1.s1",
  quote: "hello world",
  chapter: 1,
  kind: "ask",
  question: "what?",
  answer: "streaming...",
  followups: [],
  createdAt: "",
  updatedAt: "",
};
const note: Card = {
  id: "n1",
  bookId: "b",
  anchor: "p1.s2",
  quote: "nt",
  chapter: 1,
  kind: "note",
  body: "my thought",
  createdAt: "",
  updatedAt: "",
};

describe("MarginColumn", () => {
  it("renders S1 empty-state when no cards match visible anchors", () => {
    render(
      <MarginColumn
        cards={[]}
        visibleSids={new Set(["p1.s1"])}
        focusedCardId={null}
        onBodyChange={() => {}}
        onBodyCommit={() => {}}
      />,
    );
    expect(
      screen.getByRole("heading", { name: /Ask about what you're reading/i }),
    ).toBeInTheDocument();
  });

  it("filters cards by visibleSids", () => {
    render(
      <MarginColumn
        cards={[ask, note]}
        visibleSids={new Set(["p1.s1"])}
        focusedCardId={null}
        onBodyChange={() => {}}
        onBodyCommit={() => {}}
      />,
    );
    expect(screen.getByText(/streaming/)).toBeInTheDocument();
    expect(screen.queryByText(/my thought/)).not.toBeInTheDocument();
  });

  it("renders card with data-card-id for anchor lookup", () => {
    render(
      <MarginColumn
        cards={[ask]}
        visibleSids={new Set(["p1.s1"])}
        focusedCardId={null}
        onBodyChange={() => {}}
        onBodyCommit={() => {}}
      />,
    );
    expect(document.querySelector('[data-card-id="a1"]')).not.toBeNull();
  });

  it("applies focus-flash class when focusedCardId matches", () => {
    render(
      <MarginColumn
        cards={[ask]}
        visibleSids={new Set(["p1.s1"])}
        focusedCardId="a1"
        onBodyChange={() => {}}
        onBodyCommit={() => {}}
      />,
    );
    const el = document.querySelector('[data-card-id="a1"]') as HTMLElement;
    expect(el.className).toMatch(/rr-card-flash/);
  });
});
```

**Run:** FAIL.

**Implementation:**

`frontend/src/components/reader/AskCard.tsx`:

```tsx
import type { AskCard as AskCardT } from "../../lib/reader/cards";

export function AskCard({
  card,
  flash,
}: {
  card: AskCardT;
  flash: boolean;
}) {
  return (
    <article
      data-card-id={card.id}
      data-card-kind="ask"
      data-card-anchor={card.anchor}
      className={flash ? "rr-card rr-card-flash" : "rr-card"}
      style={{
        background: "var(--paper-00)",
        border: "1px solid var(--paper-2)",
        borderLeft: "3px solid var(--accent)",
        borderRadius: 10,
        padding: "14px 16px",
        boxShadow: "0 4px 12px -4px rgba(28,24,18,.08)",
        transform: "rotate(-0.2deg)",
        fontFamily: "var(--serif)",
      }}
    >
      <header
        style={{
          fontFamily: "var(--sans)",
          fontSize: 9.5,
          letterSpacing: 1.3,
          textTransform: "uppercase",
          color: "var(--accent-ink)",
          fontWeight: 600,
          marginBottom: 6,
        }}
      >
        ASKED ABOUT "{card.quote}"
      </header>
      <div
        style={{
          fontStyle: "italic",
          fontSize: 13.5,
          color: "var(--ink-1)",
          marginBottom: 6,
        }}
      >
        {card.question}
      </div>
      <div
        data-testid="ask-answer"
        style={{ fontSize: 14, lineHeight: 1.62, color: "var(--ink-0)" }}
      >
        {card.answer}
      </div>
    </article>
  );
}
```

`frontend/src/components/reader/NoteCard.tsx`:

```tsx
import { useEffect, useRef } from "react";
import type { NoteCard as NoteCardT } from "../../lib/reader/cards";

export function NoteCard({
  card,
  flash,
  autoFocus,
  onBodyChange,
  onBodyCommit,
}: {
  card: NoteCardT;
  flash: boolean;
  autoFocus: boolean;
  onBodyChange: (id: string, next: string) => void;
  onBodyCommit: (id: string) => void;
}) {
  const ref = useRef<HTMLTextAreaElement | null>(null);
  useEffect(() => {
    if (autoFocus && ref.current) ref.current.focus();
  }, [autoFocus]);

  return (
    <article
      data-card-id={card.id}
      data-card-kind="note"
      data-card-anchor={card.anchor}
      className={flash ? "rr-card rr-card-flash" : "rr-card"}
      style={{
        background: "var(--paper-00)",
        border: "1px solid var(--paper-2)",
        borderLeft: "3px solid oklch(58% 0.1 55)",
        borderRadius: 10,
        padding: "14px 16px",
        boxShadow: "0 4px 12px -4px rgba(28,24,18,.08)",
        transform: "rotate(0.2deg)",
        fontFamily: "var(--serif)",
      }}
    >
      <header
        style={{
          fontFamily: "var(--sans)",
          fontSize: 9.5,
          letterSpacing: 1.3,
          textTransform: "uppercase",
          color: "oklch(30% 0.1 55)",
          fontWeight: 600,
          marginBottom: 6,
        }}
      >
        NOTED "{card.quote}"
      </header>
      <textarea
        ref={ref}
        aria-label="Note body"
        data-testid="note-body"
        value={card.body}
        onChange={(e) => onBodyChange(card.id, e.target.value)}
        onBlur={() => onBodyCommit(card.id)}
        onKeyDown={(e) => {
          if (e.key === "Enter" && !e.shiftKey) {
            e.preventDefault();
            onBodyCommit(card.id);
          }
        }}
        placeholder="Type your note…"
        rows={3}
        style={{
          width: "100%",
          resize: "vertical",
          border: 0,
          background: "transparent",
          fontFamily: "var(--serif)",
          fontSize: 14,
          lineHeight: 1.62,
          color: "var(--ink-0)",
          outline: "none",
          padding: 0,
        }}
      />
    </article>
  );
}
```

`frontend/src/components/reader/S1EmptyCard.tsx`:

```tsx
export function S1EmptyCard() {
  return (
    <article
      data-testid="s1-empty-card"
      style={{
        background: "var(--paper-00)",
        border: "1px solid var(--paper-2)",
        borderRadius: 10,
        padding: "18px 18px 16px",
        boxShadow: "0 4px 12px -4px rgba(28,24,18,.06)",
        display: "grid",
        gridTemplateColumns: "34px 1fr",
        gap: 12,
      }}
    >
      <div
        aria-hidden="true"
        style={{
          width: 34,
          height: 34,
          borderRadius: 999,
          background: "var(--accent-softer)",
          display: "grid",
          placeItems: "center",
          color: "var(--accent-ink)",
          fontSize: 16,
        }}
      >
        ✦
      </div>
      <div>
        <h3
          style={{
            fontFamily: "var(--serif)",
            fontWeight: 500,
            fontSize: 15,
            margin: "2px 0 4px",
            color: "var(--ink-0)",
          }}
        >
          Ask about what you're reading
        </h3>
        <p
          style={{
            fontFamily: "var(--sans)",
            fontSize: 12,
            color: "var(--ink-2)",
            margin: 0,
            lineHeight: 1.5,
          }}
        >
          Select a phrase to Ask, Note, or Highlight.
        </p>
      </div>
    </article>
  );
}
```

`frontend/src/components/reader/MarginColumn.tsx`:

```tsx
import type { Card } from "../../lib/reader/cards";
import { AskCard } from "./AskCard";
import { NoteCard } from "./NoteCard";
import { S1EmptyCard } from "./S1EmptyCard";

export function MarginColumn({
  cards,
  visibleSids,
  focusedCardId,
  newlyCreatedNoteId,
  onBodyChange,
  onBodyCommit,
}: {
  cards: Card[];
  visibleSids: Set<string>;
  focusedCardId: string | null;
  newlyCreatedNoteId?: string | null;
  onBodyChange: (id: string, next: string) => void;
  onBodyCommit: (id: string) => void;
}) {
  const visible = cards.filter((c) => visibleSids.has(c.anchor));
  return (
    <aside
      aria-label="Margin cards"
      data-testid="margin-column"
      style={{
        display: "flex",
        flexDirection: "column",
        gap: 14,
        paddingTop: 40,
        width: 400,
      }}
    >
      {visible.length === 0 && <S1EmptyCard />}
      {visible.map((card) =>
        card.kind === "ask" ? (
          <AskCard key={card.id} card={card} flash={focusedCardId === card.id} />
        ) : (
          <NoteCard
            key={card.id}
            card={card}
            flash={focusedCardId === card.id}
            autoFocus={newlyCreatedNoteId === card.id}
            onBodyChange={onBodyChange}
            onBodyCommit={onBodyCommit}
          />
        ),
      )}
    </aside>
  );
}
```

Add the `rr-card-flash` CSS animation to `frontend/src/index.css` (Modify):

```css
@keyframes rr-card-flash-kf {
  0%   { box-shadow: 0 0 0 3px var(--accent-soft), 0 4px 12px -4px rgba(28,24,18,.08); }
  100% { box-shadow: 0 0 0 0 transparent, 0 4px 12px -4px rgba(28,24,18,.08); }
}
.rr-card-flash {
  animation: rr-card-flash-kf 600ms ease-out;
}
```

**Run:** `npm test -- --run src/components/reader/MarginColumn.test.tsx` → 4 green.

**Commit:**
```
git add frontend/src/components/reader/AskCard.tsx frontend/src/components/reader/NoteCard.tsx frontend/src/components/reader/S1EmptyCard.tsx frontend/src/components/reader/MarginColumn.tsx frontend/src/components/reader/MarginColumn.test.tsx frontend/src/index.css
git commit -m "Slice R2 T5: add MarginColumn, AskCard, NoteCard, S1EmptyCard"
```

---

### T6 · Extend `Sentence` with asked/noted indicators + click handler

**Goal:** Sentence accepts `marks?: { kind: 'ask' | 'note', cardId: string }[]`. Asked marks apply green background; noted marks apply orange underline. Click fires `onMarkClick(cardId)`. Fog styling unchanged.

**Files:**
- Modify: `frontend/src/components/reader/Sentence.tsx`
- Modify: `frontend/src/components/reader/Sentence.test.tsx`

**Failing test additions:**

```tsx
it("applies asked background when marks include ask", () => {
  render(
    <Sentence
      sid="p1.s1"
      text="X."
      fogged={false}
      marks={[{ kind: "ask", cardId: "a1" }]}
    />,
  );
  const el = screen.getByText("X.");
  expect(el.getAttribute("style") ?? "").toMatch(/background/);
});

it("applies underline when marks include note", () => {
  render(
    <Sentence
      sid="p1.s1"
      text="X."
      fogged={false}
      marks={[{ kind: "note", cardId: "n1" }]}
    />,
  );
  const el = screen.getByText("X.");
  expect(el.getAttribute("style") ?? "").toMatch(/underline/);
});

it("fires onMarkClick with topmost mark's cardId", async () => {
  const fn = vi.fn();
  render(
    <Sentence
      sid="p1.s1"
      text="X."
      fogged={false}
      marks={[{ kind: "ask", cardId: "a1" }]}
      onMarkClick={fn}
    />,
  );
  await userEvent.click(screen.getByText("X."));
  expect(fn).toHaveBeenCalledWith("a1");
});
```

(Add imports `userEvent`, `vi` at top.)

**Implementation** (replace `Sentence.tsx`):

```tsx
import type { CSSProperties } from "react";

export type SentenceMark = { kind: "ask" | "note"; cardId: string };

export function Sentence({
  sid,
  text,
  fogged,
  marks = [],
  onMarkClick,
}: {
  sid: string;
  text: string;
  fogged: boolean;
  marks?: SentenceMark[];
  onMarkClick?: (cardId: string) => void;
}) {
  const asked = marks.find((m) => m.kind === "ask");
  const noted = marks.find((m) => m.kind === "note");
  const style: CSSProperties = {
    transition: "opacity 180ms ease, filter 180ms ease",
    opacity: fogged ? 0.3 : 1,
    filter: fogged ? "blur(2.2px)" : "blur(0)",
    cursor: (asked || noted) && onMarkClick ? "pointer" : "inherit",
  };
  if (asked) {
    style.background = "oklch(72% 0.08 155 / 0.42)";
    style.padding = "1px 3px";
    style.borderRadius = 2;
  }
  if (noted) {
    style.textDecoration = "underline";
    style.textDecorationColor = "oklch(58% 0.1 55)";
    style.textDecorationThickness = "1.5px";
    style.textUnderlineOffset = "3px";
  }
  const onClick =
    onMarkClick && (asked || noted)
      ? () => onMarkClick((asked ?? noted)!.cardId)
      : undefined;
  return (
    <span data-sid={sid} style={style} onClick={onClick}>
      {text}
    </span>
  );
}
```

Update `Paragraph.tsx` to accept + forward `marksBySid` and `onMarkClick` (Modify):

```tsx
import { Sentence, type SentenceMark } from "./Sentence";
import type { AnchoredSentence } from "../../lib/api";
import { compareSid } from "../../lib/reader/sidCompare";

export function Paragraph({
  paragraphIdx,
  sentences,
  fogStartSid,
  dropCap,
  marksBySid,
  onMarkClick,
}: {
  paragraphIdx: number;
  sentences: AnchoredSentence[];
  fogStartSid: string | null;
  dropCap: boolean;
  marksBySid?: Map<string, SentenceMark[]>;
  onMarkClick?: (cardId: string) => void;
}) {
  return (
    <p
      data-paragraph-idx={paragraphIdx}
      className={dropCap ? "rr-para rr-dropcap" : "rr-para"}
      style={{ margin: "0 0 0.9em", textAlign: "justify", hyphens: "auto" }}
    >
      {sentences.map((s, i) => {
        const fogged = fogStartSid !== null && compareSid(s.sid, fogStartSid) > 0;
        return (
          <span key={s.sid}>
            <Sentence
              sid={s.sid}
              text={s.text}
              fogged={fogged}
              marks={marksBySid?.get(s.sid) ?? []}
              onMarkClick={onMarkClick}
            />
            {i < sentences.length - 1 ? " " : ""}
          </span>
        );
      })}
    </p>
  );
}
```

Update `BookSpread.tsx` to accept and forward `marksBySid` and `onMarkClick` into each `PageSide`, propagated into `Paragraph`. (Modify; add the two optional props, thread through.)

**Run:** `npm test -- --run src/components/reader/Sentence.test.tsx` → green (existing + 3 new).

**Commit:**
```
git add frontend/src/components/reader/Sentence.tsx frontend/src/components/reader/Sentence.test.tsx frontend/src/components/reader/Paragraph.tsx frontend/src/components/reader/BookSpread.tsx
git commit -m "Slice R2 T6: sentence-level ask/note marks with click handler"
```

---

### T7 · `useSelectionToolbar` hook (listens to `selectionchange`, produces toolbar state)

**Goal:** Hook that, given a `containerRef`, tracks the current in-container selection and exposes `{ selection, clear }`. Uses `document.selectionchange` with a 100ms debounce so the toolbar appears within the 180ms PRD window.

**Files:**
- Create: `frontend/src/lib/reader/useSelectionToolbar.ts`
- Test: `frontend/src/lib/reader/useSelectionToolbar.test.tsx`

**Failing test:**

```tsx
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { renderHook, act } from "@testing-library/react";
import { useSelectionToolbar } from "./useSelectionToolbar";
import { useRef, useEffect } from "react";

describe("useSelectionToolbar", () => {
  beforeEach(() => vi.useFakeTimers());
  afterEach(() => vi.useRealTimers());

  it("returns null when nothing is selected", () => {
    const container = document.createElement("div");
    container.innerHTML = '<span data-sid="p1.s1">Hi there.</span>';
    document.body.appendChild(container);
    const { result } = renderHook(() => {
      const ref = useRef<HTMLElement | null>(null);
      useEffect(() => {
        ref.current = container;
      }, []);
      return useSelectionToolbar(ref);
    });
    expect(result.current.selection).toBeNull();
  });

  it("captures selection anchor sid on selectionchange", async () => {
    const container = document.createElement("div");
    container.innerHTML = '<span data-sid="p1.s1">Hi there.</span>';
    document.body.appendChild(container);
    const ref = { current: container } as React.MutableRefObject<HTMLElement | null>;
    const { result } = renderHook(() => useSelectionToolbar(ref));
    const span = container.querySelector("[data-sid]")!;
    const range = document.createRange();
    range.setStart(span.firstChild!, 0);
    range.setEnd(span.firstChild!, 2);
    const sel = window.getSelection()!;
    sel.removeAllRanges();
    sel.addRange(range);
    act(() => {
      document.dispatchEvent(new Event("selectionchange"));
      vi.advanceTimersByTime(120);
    });
    expect(result.current.selection).not.toBeNull();
    expect(result.current.selection!.anchorSid).toBe("p1.s1");
    expect(result.current.selection!.quote).toBe("Hi");
  });
});
```

**Run:** FAIL.

**Implementation** (`useSelectionToolbar.ts`):

```ts
import { useEffect, useRef, useState, type MutableRefObject } from "react";
import { computeSelection, type ComputedSelection } from "./selection";

export function useSelectionToolbar(
  containerRef: MutableRefObject<HTMLElement | null>,
) {
  const [selection, setSelection] = useState<ComputedSelection | null>(null);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    function schedule() {
      if (timer.current) clearTimeout(timer.current);
      timer.current = setTimeout(() => {
        const container = containerRef.current;
        if (!container) {
          setSelection(null);
          return;
        }
        const sel = window.getSelection();
        if (!sel || sel.rangeCount === 0) {
          setSelection(null);
          return;
        }
        const range = sel.getRangeAt(0);
        setSelection(computeSelection(range, container));
      }, 100);
    }
    document.addEventListener("selectionchange", schedule);
    return () => {
      document.removeEventListener("selectionchange", schedule);
      if (timer.current) clearTimeout(timer.current);
    };
  }, [containerRef]);

  return {
    selection,
    clear: () => {
      window.getSelection()?.removeAllRanges();
      setSelection(null);
    },
  };
}
```

**Run:** 2 green.

**Commit:**
```
git add frontend/src/lib/reader/useSelectionToolbar.ts frontend/src/lib/reader/useSelectionToolbar.test.tsx
git commit -m "Slice R2 T7: add useSelectionToolbar hook"
```

---

### T8 · Wire Ask action to `POST /books/{id}/query` + simulated streaming

**Goal:** Introduce a thin `askAndStream` helper that creates an ask card synchronously, calls `queryBook`, and feeds the response answer through `simulateStream` into `updateAsk`. Covers duplicate detection: if a card with same `anchor` and `kind: "ask"` exists, return its id without creating.

**Files:**
- Create: `frontend/src/lib/reader/askFlow.ts`
- Test: `frontend/src/lib/reader/askFlow.test.ts`

**Failing test:**

```ts
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { askAndStream, buildAskQuestion } from "./askFlow";

describe("buildAskQuestion", () => {
  it("embeds quote in prompt", () => {
    expect(buildAskQuestion("freedom")).toBe(
      'Asked about "freedom": what does this mean in context?',
    );
  });
});

describe("askAndStream", () => {
  beforeEach(() => vi.useFakeTimers());
  afterEach(() => vi.useRealTimers());

  it("creates a new ask card and streams the answer into it", async () => {
    const createAsk = vi.fn(() => "card-1");
    const updateAsk = vi.fn();
    const queryBook = vi.fn(async () => ({
      answer: "The answer is forty two",
      results: [],
      result_count: 0,
      book_id: "b",
      question: "q",
      search_type: "GRAPH_COMPLETION",
      current_chapter: 1,
    }));
    const findExisting = vi.fn(() => undefined);

    const p = askAndStream({
      anchor: "p1.s1",
      quote: "freedom",
      chapter: 1,
      maxChapter: 1,
      bookId: "b",
      createAsk,
      updateAsk,
      findExisting,
      queryBook,
      streamMinMs: 5,
      streamMaxMs: 5,
    });
    await vi.runAllTimersAsync();
    const id = await p;
    expect(id).toBe("card-1");
    expect(createAsk).toHaveBeenCalledWith({
      anchor: "p1.s1",
      quote: "freedom",
      chapter: 1,
      question: 'Asked about "freedom": what does this mean in context?',
    });
    expect(queryBook).toHaveBeenCalled();
    expect(updateAsk).toHaveBeenCalled();
  });

  it("returns existing card id without creating when duplicate detected", async () => {
    const createAsk = vi.fn(() => "new");
    const updateAsk = vi.fn();
    const findExisting = vi.fn(() => ({ id: "existing" }));
    const queryBook = vi.fn();
    const id = await askAndStream({
      anchor: "p1.s1",
      quote: "x",
      chapter: 1,
      maxChapter: 1,
      bookId: "b",
      createAsk,
      updateAsk,
      findExisting,
      queryBook,
    });
    expect(id).toBe("existing");
    expect(createAsk).not.toHaveBeenCalled();
    expect(queryBook).not.toHaveBeenCalled();
  });
});
```

**Run:** FAIL.

**Implementation** (`askFlow.ts`):

```ts
import { simulateStream } from "./streamSimulator";
import type { AskCard } from "./cards";

export function buildAskQuestion(quote: string): string {
  return `Asked about "${quote}": what does this mean in context?`;
}

export interface AskFlowInput {
  anchor: string;
  quote: string;
  chapter: number;
  maxChapter: number;
  bookId: string;
  createAsk: (input: {
    anchor: string;
    quote: string;
    chapter: number;
    question: string;
  }) => string;
  updateAsk: (id: string, updater: (prev: AskCard) => AskCard) => void;
  findExisting: (anchor: string) => { id: string } | undefined;
  queryBook: (
    bookId: string,
    question: string,
    maxChapter: number,
  ) => Promise<{ answer: string }>;
  streamMinMs?: number;
  streamMaxMs?: number;
  signal?: AbortSignal;
}

export async function askAndStream(input: AskFlowInput): Promise<string> {
  const existing = input.findExisting(input.anchor);
  if (existing) return existing.id;

  const question = buildAskQuestion(input.quote);
  const id = input.createAsk({
    anchor: input.anchor,
    quote: input.quote,
    chapter: input.chapter,
    question,
  });
  const resp = await input.queryBook(input.bookId, question, input.maxChapter);
  const full = resp.answer ?? "";
  await simulateStream(full, {
    minMs: input.streamMinMs ?? 25,
    maxMs: input.streamMaxMs ?? 60,
    signal: input.signal,
    onChunk: (soFar) =>
      input.updateAsk(id, (prev) => ({ ...prev, answer: soFar })),
  });
  return id;
}
```

**Run:** 3 green.

**Commit:**
```
git add frontend/src/lib/reader/askFlow.ts frontend/src/lib/reader/askFlow.test.ts
git commit -m "Slice R2 T8: add askAndStream with duplicate detection"
```

---

### T9 · ReadingScreen integration (margin column, selection, ask/note wiring, scroll-to-card)

**Goal:** Update `ReadingScreen` to:
- Grid layout `1fr 400px` in the stage.
- Compute `visibleSids` from current spread.
- Manage selection via `useSelectionToolbar`; render `SelectionToolbar` with fog-of-war disabled state for Ask when `selection.anchorSid > cursor`.
- On Ask: call `askAndStream` with `queryBook` from `lib/api`; focus/flash the new card.
- On Note: `createNote` then set a `newlyCreatedNoteId` to autofocus; commit on blur/Enter (empty → `removeCard`).
- On Highlight: clear selection, no-op.
- Click an on-page indicator → scroll margin card into view + set `focusedCardId` for 600ms (CSS flash).
- Pass `marksBySid` (computed from cards filtered by `visibleSids`) into `BookSpread`.

**Files:**
- Modify: `frontend/src/screens/ReadingScreen.tsx`
- Modify: `frontend/src/screens/ReadingScreen.test.tsx` (may need updates for new structure)

**Failing test** (additions to `ReadingScreen.test.tsx`):

```tsx
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, act, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Routes, Route } from "react-router-dom";
import { ReadingScreen } from "./ReadingScreen";
import * as api from "../lib/api";

function renderAt(path: string) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route
          path="/books/:bookId/read/:chapterNum"
          element={<ReadingScreen />}
        />
      </Routes>
    </MemoryRouter>,
  );
}

describe("ReadingScreen (R2 integration)", () => {
  beforeEach(() => {
    window.localStorage.clear();
    vi.spyOn(api, "fetchChapter").mockResolvedValue({
      num: 1,
      title: "C1",
      total_chapters: 1,
      has_prev: false,
      has_next: false,
      paragraphs: ["x"],
      paragraphs_anchored: [
        {
          paragraph_idx: 1,
          sentences: [
            { sid: "p1.s1", text: "Alpha sentence here." },
            { sid: "p1.s2", text: "Bravo sentence here." },
          ],
        },
      ],
      anchors_fallback: false,
    });
  });

  it("renders MarginColumn with S1 empty when no cards", async () => {
    renderAt("/books/carol/read/1");
    await waitFor(() =>
      expect(screen.getByTestId("margin-column")).toBeInTheDocument(),
    );
    expect(screen.getByTestId("s1-empty-card")).toBeInTheDocument();
  });
});
```

**Run:** FAIL (no margin-column testid in current ReadingScreen).

**Implementation** (`ReadingScreen.tsx`, excerpted core changes — full file retained but key new/modified code):

```tsx
// New imports
import { SelectionToolbar, type SelectionAction } from "../components/SelectionToolbar";
import { MarginColumn } from "../components/reader/MarginColumn";
import { useCards } from "../lib/reader/useCards";
import { useSelectionToolbar } from "../lib/reader/useSelectionToolbar";
import { askAndStream } from "../lib/reader/askFlow";
import { queryBook } from "../lib/api";
import { compareSid } from "../lib/reader/sidCompare";
import type { SentenceMark } from "../components/reader/Sentence";

// Inside ReadingScreen component:
const bookRef = useRef<HTMLDivElement | null>(null);
const {
  cards,
  createAsk,
  createNote,
  updateAsk,
  updateNote,
  removeCard,
  findByAnchorAndKind,
} = useCards(bookId);
const { selection, clear: clearSelection } = useSelectionToolbar(bookRef);

const [focusedCardId, setFocusedCardId] = useState<string | null>(null);
const [newlyCreatedNoteId, setNewlyCreatedNoteId] = useState<string | null>(null);
const flashTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
const flash = useCallback((id: string) => {
  setFocusedCardId(id);
  if (flashTimer.current) clearTimeout(flashTimer.current);
  flashTimer.current = setTimeout(() => setFocusedCardId(null), 620);
}, []);

const visibleSids: Set<string> = useMemo(() => {
  if (!current) return new Set();
  const s = new Set<string>();
  for (const page of [current.left, current.right]) {
    for (const para of page) {
      for (const sent of para.sentences) s.add(sent.sid);
    }
  }
  return s;
}, [current]);

const marksBySid: Map<string, SentenceMark[]> = useMemo(() => {
  const m = new Map<string, SentenceMark[]>();
  for (const c of cards) {
    if (!visibleSids.has(c.anchor)) continue;
    const arr = m.get(c.anchor) ?? [];
    arr.push({ kind: c.kind, cardId: c.id });
    m.set(c.anchor, arr);
  }
  return m;
}, [cards, visibleSids]);

const onMarkClick = useCallback(
  (cardId: string) => {
    const el = document.querySelector(`[data-card-id="${cardId}"]`);
    if (el) el.scrollIntoView({ behavior: "smooth", block: "center" });
    flash(cardId);
  },
  [flash],
);

const onAction = useCallback(
  async (action: SelectionAction) => {
    if (!selection) return;
    const { anchorSid, quote } = selection;
    const chapter = n;
    if (action === "highlight") {
      clearSelection();
      return;
    }
    if (action === "note") {
      const existing = findByAnchorAndKind(anchorSid, "note");
      if (existing) {
        flash(existing.id);
        clearSelection();
        return;
      }
      const id = createNote({ anchor: anchorSid, quote, chapter });
      setNewlyCreatedNoteId(id);
      flash(id);
      clearSelection();
      return;
    }
    // ask
    const existing = findByAnchorAndKind(anchorSid, "ask");
    if (existing) {
      flash(existing.id);
      clearSelection();
      return;
    }
    clearSelection();
    const id = await askAndStream({
      anchor: anchorSid,
      quote,
      chapter,
      maxChapter: chapter,
      bookId,
      createAsk,
      updateAsk,
      findExisting: (a) => {
        const e = findByAnchorAndKind(a, "ask");
        return e ? { id: e.id } : undefined;
      },
      queryBook: (b, q, mc) => queryBook(b, q, mc),
    });
    flash(id);
  },
  [selection, n, bookId, clearSelection, findByAnchorAndKind, flash, createNote, createAsk, updateAsk],
);

const onBodyChange = useCallback(
  (id: string, next: string) => updateNote(id, next),
  [updateNote],
);
const onBodyCommit = useCallback(
  (id: string) => {
    const card = cards.find((c) => c.id === id);
    if (card && card.kind === "note" && card.body.trim() === "") {
      removeCard(id);
    }
    setNewlyCreatedNoteId((prev) => (prev === id ? null : prev));
  },
  [cards, removeCard],
);

// Fog check for Ask button disabled state:
const askDisabled =
  !!selection && compareSid(selection.anchorSid, cursor) > 0;
```

JSX stage replaces the `<div style={{ width: "min(1100px, 100%)" }}>` block:

```tsx
{body.kind === "ok" && current && (
  <div
    style={{
      display: "grid",
      gridTemplateColumns: "1fr 400px",
      gap: 28,
      alignItems: "start",
      width: "min(1240px, 100%)",
    }}
  >
    <div ref={bookRef}>
      <BookSpread
        chapterNum={body.chapter.num}
        chapterTitle={body.chapter.title}
        totalChapters={total}
        left={current.left}
        right={current.right}
        folioLeft={spreadIdx * 2 + 1}
        folioRight={spreadIdx * 2 + 2}
        cursor={cursor}
        isFirstSpread={spreadIdx === 0}
        marksBySid={marksBySid}
        onMarkClick={onMarkClick}
      />
    </div>
    <MarginColumn
      cards={cards}
      visibleSids={visibleSids}
      focusedCardId={focusedCardId}
      newlyCreatedNoteId={newlyCreatedNoteId}
      onBodyChange={onBodyChange}
      onBodyCommit={onBodyCommit}
    />
  </div>
)}
{selection && (
  <SelectionToolbar
    top={selection.rect.top + window.scrollY}
    left={selection.rect.left + selection.rect.width / 2 + window.scrollX}
    onAction={onAction}
    disabled={{ ask: askDisabled }}
  />
)}
```

**Run:** `npm test -- --run src/screens/ReadingScreen.test.tsx` → green.

**Commit:**
```
git add frontend/src/screens/ReadingScreen.tsx frontend/src/screens/ReadingScreen.test.tsx
git commit -m "Slice R2 T9: integrate margin column, selection toolbar, ask and note flows"
```

---

### T10 · Delete legacy components (orphan sweep)

**Goal:** Remove legacy annotation scaffolding (`AnnotationRail`, `AnnotationPanel`, `AnnotationPeek`, `NoteComposer`, `AnnotatedParagraph`, `useAnnotations`) and their tests. Verify no remaining imports across `frontend/src` and `frontend/e2e`.

**Files:**
- Delete: `frontend/src/components/AnnotationRail.tsx`
- Delete: `frontend/src/components/AnnotationPanel.tsx`
- Delete: `frontend/src/components/AnnotationPeek.tsx`
- Delete: `frontend/src/components/NoteComposer.tsx`
- Delete: `frontend/src/components/AnnotatedParagraph.tsx`
- Delete: `frontend/src/screens/reading/useAnnotations.ts`
- Delete: `frontend/src/screens/reading/useAnnotations.test.tsx`

**Failing test (proxy):** run `npm test -- --run` expecting all currently passing; then delete files. Before deletion, grep to confirm no live imports from R1-integrated code:

```
grep -rln "AnnotationRail\|AnnotationPanel\|AnnotationPeek\|NoteComposer\|AnnotatedParagraph\|useAnnotations" frontend/src frontend/e2e
```
Expected output after T9 landed: only the files being deleted themselves (plus their tests).

**Run:** first `npm test -- --run` → all green with legacy files present. Then delete. Re-run `npm test -- --run` and `npx tsc --noEmit` → green (no orphan imports).

**Commit:**
```
git rm frontend/src/components/AnnotationRail.tsx frontend/src/components/AnnotationPanel.tsx frontend/src/components/AnnotationPeek.tsx frontend/src/components/NoteComposer.tsx frontend/src/components/AnnotatedParagraph.tsx frontend/src/screens/reading/useAnnotations.ts frontend/src/screens/reading/useAnnotations.test.tsx
git commit -m "Slice R2 T10: delete legacy annotation components replaced by V3 Inline"
```

---

### T11 · Playwright spec: `slice-R2-cards-and-selection.spec.ts`

**Goal:** Tests mapping 1:1 to PRD acceptance criteria (3, 5, 6, 7, 9, 10, 12, 13).

**Files:**
- Create: `frontend/e2e/slice-R2-cards-and-selection.spec.ts`

**Failing test** (verbatim):

```ts
import { test, expect, type Page, type Route } from "@playwright/test";

const BOOK_ID = "carol";

function makeChapter(n: number) {
  const paragraphs_anchored = [
    {
      paragraph_idx: 1,
      sentences: [
        { sid: "p1.s1", text: "Alpha sentence padded with more words for selection." },
        { sid: "p1.s2", text: "Bravo sentence padded with more words for selection." },
        { sid: "p1.s3", text: "Gamma sentence padded with more words for selection." },
      ],
    },
  ];
  const paragraphs = paragraphs_anchored.map((p) =>
    p.sentences.map((s) => s.text).join(" "),
  );
  return {
    num: n,
    title: `Chapter ${n}`,
    total_chapters: 1,
    has_prev: false,
    has_next: false,
    paragraphs,
    paragraphs_anchored,
    anchors_fallback: false,
  };
}

async function mockAll(page: Page) {
  await page.route("http://localhost:8000/books", async (route: Route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify([
        {
          book_id: BOOK_ID,
          title: "Carol",
          total_chapters: 1,
          current_chapter: 1,
          ready_for_query: true,
        },
      ]),
    });
  });
  await page.route(
    new RegExp(`^http://localhost:8000/books/${BOOK_ID}/chapters/(\\d+)$`),
    async (route: Route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(makeChapter(1)),
      });
    },
  );
  await page.route(
    `http://localhost:8000/books/${BOOK_ID}/query`,
    async (route: Route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          book_id: BOOK_ID,
          question: "q",
          search_type: "GRAPH_COMPLETION",
          current_chapter: 1,
          answer:
            "This is a synthesized answer with enough words to observe streaming chunks landing over time.",
          results: [],
          result_count: 0,
        }),
      });
    },
  );
}

async function selectInSid(page: Page, sid: string) {
  await page.evaluate((s) => {
    const el = document.querySelector(`[data-sid="${s}"]`) as HTMLElement;
    const text = el.firstChild!;
    const range = document.createRange();
    range.setStart(text, 0);
    range.setEnd(text, 5);
    const sel = window.getSelection()!;
    sel.removeAllRanges();
    sel.addRange(range);
    document.dispatchEvent(new Event("selectionchange"));
  }, sid);
}

test.describe("Slice R2 — margin cards, selection, ask, note", () => {
  test.beforeEach(async ({ page }) => {
    await mockAll(page);
  });

  test("selection shows the Ask/Note/Highlight toolbar (AC 3)", async ({ page }) => {
    await page.goto(`/books/${BOOK_ID}/read/1`);
    await expect(page.getByTestId("book-spread")).toBeVisible();
    await selectInSid(page, "p1.s1");
    await expect(page.getByTestId("selection-toolbar")).toBeVisible({
      timeout: 1000,
    });
    await expect(page.getByRole("button", { name: "Ask" })).toBeVisible();
    await expect(page.getByRole("button", { name: "Note" })).toBeVisible();
    await expect(page.getByRole("button", { name: "Highlight" })).toBeVisible();
  });

  test("Ask creates a card whose answer grows and ends non-empty (AC 5, 6)", async ({ page }) => {
    await page.goto(`/books/${BOOK_ID}/read/1`);
    await expect(page.getByTestId("book-spread")).toBeVisible();
    await selectInSid(page, "p1.s1");
    await page.getByRole("button", { name: "Ask" }).click();
    const answer = page.getByTestId("ask-answer").first();
    await expect(answer).toBeVisible();
    // Eventually the final answer lands.
    await expect(answer).toContainText("synthesized answer", { timeout: 5000 });
  });

  test("Note creates a card, accepts typed body, persists on Enter (AC 7, 12)", async ({ page }) => {
    await page.goto(`/books/${BOOK_ID}/read/1`);
    await expect(page.getByTestId("book-spread")).toBeVisible();
    await selectInSid(page, "p1.s1");
    await page.getByRole("button", { name: "Note" }).click();
    const body = page.getByTestId("note-body").first();
    await expect(body).toBeFocused();
    await body.fill("my annotation");
    await body.press("Enter");
    const stored = await page.evaluate(() =>
      window.localStorage.getItem(`bookrag.cards.${"carol"}`),
    );
    expect(stored).not.toBeNull();
    expect(stored!).toContain("my annotation");
  });

  test("reload restores cards (AC 12)", async ({ page }) => {
    await page.goto(`/books/${BOOK_ID}/read/1`);
    await expect(page.getByTestId("book-spread")).toBeVisible();
    await selectInSid(page, "p1.s2");
    await page.getByRole("button", { name: "Note" }).click();
    await page.getByTestId("note-body").first().fill("persist me");
    await page.getByTestId("note-body").first().press("Enter");
    await page.reload();
    await expect(page.getByTestId("book-spread")).toBeVisible();
    await expect(page.getByText("persist me")).toBeVisible();
  });

  test("asked sentence shows green highlight, clicking it focuses the card (AC 9, 10)", async ({ page }) => {
    await page.goto(`/books/${BOOK_ID}/read/1`);
    await expect(page.getByTestId("book-spread")).toBeVisible();
    await selectInSid(page, "p1.s1");
    await page.getByRole("button", { name: "Ask" }).click();
    // Wait for streaming to finish so the card is stable.
    await expect(page.getByTestId("ask-answer").first()).toContainText(
      "synthesized answer",
      { timeout: 5000 },
    );
    const sentence = page.locator('[data-sid="p1.s1"]').first();
    const bg = await sentence.evaluate((el) => getComputedStyle(el).backgroundColor);
    // oklch(72% 0.08 155 / 0.42) resolves to non-transparent.
    expect(bg).not.toBe("rgba(0, 0, 0, 0)");
    await sentence.click();
    const card = page.locator("[data-card-kind='ask']").first();
    await expect(card).toHaveClass(/rr-card-flash/);
  });

  test("Ask is disabled when selection is past the fog cursor (AC 13)", async ({ page }) => {
    await page.goto(`/books/${BOOK_ID}/read/1`);
    await expect(page.getByTestId("book-spread")).toBeVisible();
    // Initial cursor = p1.s1; selecting in p1.s2 is past the cursor.
    await selectInSid(page, "p1.s2");
    const ask = page.getByRole("button", { name: "Ask" });
    await expect(ask).toBeDisabled();
    // Note remains enabled.
    await expect(page.getByRole("button", { name: "Note" })).toBeEnabled();
  });
});
```

**Run:** `cd frontend && npx playwright test slice-R2-cards-and-selection.spec.ts`
Expected initial FAIL in pure red-green mode would be before T9; after T9 + T10 the full suite should pass. If any spec fails at this point, fix the underlying integration before committing.

**Commit:**
```
git add frontend/e2e/slice-R2-cards-and-selection.spec.ts
git commit -m "Slice R2 T11: Playwright evaluator spec for margin cards and selection flows"
```

---

### T12 · Final verification sweep

**Goal:** Confirm the full suite is green with no orphans and the backend is untouched.

**Files:** none.

**Steps:**

1. `cd frontend && npm test -- --run` → all green.
2. `cd frontend && npx tsc --noEmit` → clean.
3. `cd frontend && npx playwright test` → all specs green (R1 + R2 + preexisting).
4. `source .venv/bin/activate && python -m pytest tests/ -v --tb=short` → unchanged, all green (no backend changes).
5. `grep -rln "AnnotationRail\|AnnotationPanel\|AnnotationPeek\|NoteComposer\|AnnotatedParagraph\|useAnnotations" frontend/src frontend/e2e` → empty output.

No commit unless a fix landed here; if a trailing fix was needed, commit as:

```
git commit -m "Slice R2 T12: final verification fixes"
```

---

## Summary

Plan: **12 tasks**, all test-first, each 30–90 minutes. Frontend creates 13 files (`cards.ts`, `useCards.ts` + test, `streamSimulator.ts` + test, `selection.ts` + test, `useSelectionToolbar.ts` + test, `askFlow.ts` + test, `MarginColumn.tsx` + test, `AskCard.tsx`, `NoteCard.tsx`, `S1EmptyCard.tsx`, `SelectionToolbar.test.tsx`, plus the Playwright spec); modifies 6 files (`ReadingScreen.tsx` + test, `SelectionToolbar.tsx`, `Sentence.tsx` + test, `Paragraph.tsx`, `BookSpread.tsx`, `index.css`); deletes 7 legacy files (`AnnotationRail.tsx`, `AnnotationPanel.tsx`, `AnnotationPeek.tsx`, `NoteComposer.tsx`, `AnnotatedParagraph.tsx`, `useAnnotations.ts`, `useAnnotations.test.tsx`). Backend files touched: **none** — R2 consumes the existing `POST /books/{book_id}/query` unchanged and simulates streaming client-side. The evaluator gate lives at `/Users/jeffreykrapf/Documents/thefinalbookrag/frontend/e2e/slice-R2-cards-and-selection.spec.ts`.
