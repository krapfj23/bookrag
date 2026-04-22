import { useCallback, useEffect, useRef, useState } from "react";
import {
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
