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
