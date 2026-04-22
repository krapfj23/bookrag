import { describe, it, expect, beforeEach } from "vitest";
import {
  CARDS_KEY,
  readStoredCards,
  writeStoredCards,
  type AskCard,
  type Card,
  type NoteCard,
} from "./cards";

const BOOK = "book-strip";

function makeAsk(overrides: Partial<AskCard> = {}): AskCard {
  return {
    id: "a1",
    bookId: BOOK,
    anchor: "p1.s1",
    quote: "q",
    chapter: 1,
    kind: "ask",
    question: "Q?",
    answer: "A",
    followups: [],
    createdAt: "2026-04-22T00:00:00Z",
    updatedAt: "2026-04-22T00:00:00Z",
    ...overrides,
  };
}

function makeNote(overrides: Partial<NoteCard> = {}): NoteCard {
  return {
    id: "n1",
    bookId: BOOK,
    anchor: "p1.s2",
    quote: "q",
    chapter: 1,
    kind: "note",
    body: "body",
    createdAt: "2026-04-22T00:00:00Z",
    updatedAt: "2026-04-22T00:00:00Z",
    ...overrides,
  };
}

describe("writeStoredCards — transient flag stripping", () => {
  beforeEach(() => window.localStorage.clear());

  it("strips loading flag before persisting an ask card", () => {
    const card = makeAsk({ loading: true } as Partial<AskCard>);
    writeStoredCards(BOOK, [card as Card]);
    const raw = window.localStorage.getItem(CARDS_KEY(BOOK))!;
    const parsed = JSON.parse(raw);
    expect(parsed.cards[0].loading).toBeUndefined();
  });

  it("strips streaming flag before persisting an ask card", () => {
    const card = makeAsk({ streaming: true } as Partial<AskCard>);
    writeStoredCards(BOOK, [card as Card]);
    const parsed = JSON.parse(window.localStorage.getItem(CARDS_KEY(BOOK))!);
    expect(parsed.cards[0].streaming).toBeUndefined();
  });

  it("strips followupLoading flag before persisting an ask card", () => {
    const card = makeAsk({ followupLoading: true } as Partial<AskCard>);
    writeStoredCards(BOOK, [card as Card]);
    const parsed = JSON.parse(window.localStorage.getItem(CARDS_KEY(BOOK))!);
    expect(parsed.cards[0].followupLoading).toBeUndefined();
  });

  it("preserves persistent fields on an ask card when stripping flags", () => {
    const card = makeAsk({
      loading: true,
      streaming: true,
      followupLoading: true,
    } as Partial<AskCard>);
    writeStoredCards(BOOK, [card as Card]);
    const read = readStoredCards(BOOK);
    expect(read).toHaveLength(1);
    const stored = read[0] as AskCard;
    expect(stored.kind).toBe("ask");
    expect(stored.answer).toBe("A");
    expect(stored.question).toBe("Q?");
    expect(stored.followups).toEqual([]);
    // Transient flags absent on re-read
    expect((stored as AskCard & { loading?: boolean }).loading).toBeUndefined();
    expect(
      (stored as AskCard & { streaming?: boolean }).streaming,
    ).toBeUndefined();
    expect(
      (stored as AskCard & { followupLoading?: boolean }).followupLoading,
    ).toBeUndefined();
  });

  it("does not mutate the original card object passed to writeStoredCards", () => {
    const card = makeAsk({ loading: true } as Partial<AskCard>);
    writeStoredCards(BOOK, [card as Card]);
    expect((card as AskCard & { loading?: boolean }).loading).toBe(true);
  });

  it("leaves NoteCard untouched", () => {
    const note = makeNote();
    writeStoredCards(BOOK, [note]);
    const read = readStoredCards(BOOK);
    expect(read).toHaveLength(1);
    expect(read[0]).toMatchObject({ kind: "note", body: "body" });
  });

  it("re-reading after write returns no loading key on any ask card", () => {
    const a1 = makeAsk({ id: "a1", loading: true } as Partial<AskCard>);
    const a2 = makeAsk({ id: "a2", streaming: true } as Partial<AskCard>);
    writeStoredCards(BOOK, [a1 as Card, a2 as Card]);
    const raw = window.localStorage.getItem(CARDS_KEY(BOOK))!;
    const parsed = JSON.parse(raw);
    for (const c of parsed.cards) {
      expect("loading" in c).toBe(false);
      expect("streaming" in c).toBe(false);
      expect("followupLoading" in c).toBe(false);
    }
  });
});
