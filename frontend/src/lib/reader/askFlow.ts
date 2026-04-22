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
  setAskLoading?: (id: string, loading: boolean) => void;
  setAskStreaming?: (id: string, streaming: boolean) => void;
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

  input.setAskLoading?.(id, true);

  const resp = await input.queryBook(input.bookId, question, input.maxChapter);
  const full = resp.answer ?? "";

  let firstChunk = true;
  await simulateStream(full, {
    minMs: input.streamMinMs ?? 25,
    maxMs: input.streamMaxMs ?? 60,
    signal: input.signal,
    onChunk: (soFar) => {
      if (firstChunk) {
        firstChunk = false;
        input.setAskLoading?.(id, false);
        input.setAskStreaming?.(id, true);
      }
      input.updateAsk(id, (prev) => ({ ...prev, answer: soFar }));
    },
  });
  // Use setTimeout to ensure streaming=false is scheduled in a separate
  // React batch from the final chunk, so the cursor remains visible briefly.
  await new Promise<void>((r) => setTimeout(r, 0));
  input.setAskStreaming?.(id, false);
  return id;
}

export interface FollowupFlowInput {
  cardId: string;
  bookId: string;
  maxChapter: number;
  question: string;
  appendFollowup: (id: string, question: string, initialAnswer: string) => void;
  updateAsk: (id: string, updater: (prev: AskCard) => AskCard) => void;
  queryBook: (
    bookId: string,
    question: string,
    maxChapter: number,
  ) => Promise<{ answer: string }>;
  setFollowupLoading?: (id: string, loading: boolean) => void;
  streamMinMs?: number;
  streamMaxMs?: number;
  signal?: AbortSignal;
}

export async function followupAndStream(input: FollowupFlowInput): Promise<void> {
  const { cardId, bookId, maxChapter, question } = input;

  input.appendFollowup(cardId, question, "");
  input.setFollowupLoading?.(cardId, true);

  const resp = await input.queryBook(bookId, question, maxChapter);
  const full = resp.answer ?? "";

  await simulateStream(full, {
    minMs: input.streamMinMs ?? 25,
    maxMs: input.streamMaxMs ?? 60,
    signal: input.signal,
    onChunk: (soFar) => {
      input.updateAsk(cardId, (prev) => ({
        ...prev,
        followups: prev.followups.map((f, i, arr) =>
          i === arr.length - 1 ? { ...f, answer: soFar } : f,
        ),
      }));
    },
  });

  input.setFollowupLoading?.(cardId, false);
}
