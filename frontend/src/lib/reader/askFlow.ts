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
