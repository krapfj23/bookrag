import { useCallback, useEffect, useRef, useState } from "react";
import {
  newCardId,
  readStoredCards,
  writeStoredCards,
  type AskCard,
  type Card,
  type HighlightCard,
  type NoteCard,
} from "./cards";

export { CARDS_KEY } from "./cards";
export type { Card, AskCard, NoteCard, HighlightCard } from "./cards";

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

  // Write to localStorage and update React state.
  // Note: always writes the passed `next` (not re-reading state).
  const commitDirect = useCallback(
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
      commitDirect([...readStoredCards(bookId), card]);
      return card.id;
    },
    [bookId, commitDirect],
  );

  const createHighlight = useCallback(
    (input: CreateNoteInput): string => {
      const now = new Date().toISOString();
      const card: HighlightCard = {
        id: newCardId(),
        bookId,
        anchor: input.anchor,
        quote: input.quote,
        chapter: input.chapter,
        kind: "highlight",
        createdAt: now,
        updatedAt: now,
      };
      commitDirect([...readStoredCards(bookId), card]);
      return card.id;
    },
    [bookId, commitDirect],
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
      commitDirect([...readStoredCards(bookId), card]);
      return card.id;
    },
    [bookId, commitDirect],
  );

  // updateAsk uses a functional state update to read from CURRENT React state
  // (not localStorage) so that transient in-memory flags (loading, streaming)
  // are preserved across rapid successive calls.
  const updateAsk = useCallback(
    (id: string, updater: (prev: AskCard) => AskCard) => {
      setCards((current) => {
        const next = current.map((c) => {
          if (c.id !== id || c.kind !== "ask") return c;
          const updated = updater(c);
          return { ...updated, updatedAt: new Date().toISOString() };
        });
        // Persist to localStorage (strips transient flags).
        writeStoredCards(bookId, next);
        return next;
      });
    },
    [bookId],
  );

  const updateNote = useCallback(
    (id: string, body: string) => {
      const current = readStoredCards(bookId);
      const next = current.map((c) => {
        if (c.id !== id || c.kind !== "note") return c;
        return { ...c, body, updatedAt: new Date().toISOString() };
      });
      commitDirect(next);
    },
    [bookId, commitDirect],
  );

  const removeCard = useCallback(
    (id: string) => {
      commitDirect(readStoredCards(bookId).filter((c) => c.id !== id));
    },
    [bookId, commitDirect],
  );

  const findByAnchorAndKind = useCallback(
    (anchor: string, kind: Card["kind"]): Card | undefined =>
      cards.find((c) => c.anchor === anchor && c.kind === kind),
    [cards],
  );

  const appendFollowup = useCallback(
    (id: string, question: string, initialAnswer = "") => {
      updateAsk(id, (prev) => ({
        ...prev,
        followups: [...prev.followups, { question, answer: initialAnswer }],
      }));
    },
    [updateAsk],
  );

  const setAskLoading = useCallback(
    (id: string, loading: boolean) => {
      updateAsk(id, (prev) => ({ ...prev, loading }));
    },
    [updateAsk],
  );

  const setAskStreaming = useCallback(
    (id: string, streaming: boolean) => {
      updateAsk(id, (prev) => ({ ...prev, streaming }));
    },
    [updateAsk],
  );

  return {
    cards,
    createAsk,
    createHighlight,
    createNote,
    updateAsk,
    updateNote,
    removeCard,
    findByAnchorAndKind,
    appendFollowup,
    setAskLoading,
    setAskStreaming,
  };
}
