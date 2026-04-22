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
