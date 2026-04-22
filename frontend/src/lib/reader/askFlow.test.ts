import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import {
  askAndStream,
  buildAskQuestion,
  followupAndStream,
} from "./askFlow";
import type { AskCard } from "./cards";

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

  it("drives loading=true then loading=false+streaming=true on first chunk, streaming=false at end", async () => {
    const createAsk = vi.fn(() => "card-1");
    const updateAsk = vi.fn();
    const setAskLoading = vi.fn();
    const setAskStreaming = vi.fn();
    const findExisting = vi.fn(() => undefined);
    const queryBook = vi.fn(async () => ({
      answer: "hello world here",
    }));

    const events: Array<[string, boolean]> = [];
    setAskLoading.mockImplementation((_id: string, v: boolean) =>
      events.push(["loading", v]),
    );
    setAskStreaming.mockImplementation((_id: string, v: boolean) =>
      events.push(["streaming", v]),
    );

    const p = askAndStream({
      anchor: "p1.s1",
      quote: "hello",
      chapter: 1,
      maxChapter: 1,
      bookId: "b",
      createAsk,
      updateAsk,
      findExisting,
      queryBook,
      setAskLoading,
      setAskStreaming,
      streamMinMs: 1,
      streamMaxMs: 1,
    });
    await vi.runAllTimersAsync();
    await p;

    // loading=true must be emitted before any streaming event.
    expect(events[0]).toEqual(["loading", true]);
    // At some point loading flips false and streaming flips true (first chunk).
    const loadFalseIdx = events.findIndex(
      (e) => e[0] === "loading" && e[1] === false,
    );
    const streamTrueIdx = events.findIndex(
      (e) => e[0] === "streaming" && e[1] === true,
    );
    expect(loadFalseIdx).toBeGreaterThan(-1);
    expect(streamTrueIdx).toBeGreaterThan(-1);
    // Final event: streaming=false.
    expect(events[events.length - 1]).toEqual(["streaming", false]);
  });

  it("followupAndStream appends followup pre-stream and grows its answer", async () => {
    const appendFollowup = vi.fn();
    const updateAsk = vi.fn();
    const queryBook = vi.fn(async () => ({ answer: "because reasons" }));
    const captured: AskCard[] = [];
    // Build a minimal AskCard state updater capture: updateAsk receives updater fn.
    let fakeCard: AskCard = {
      id: "card-x",
      bookId: "b",
      anchor: "p1.s1",
      quote: "q",
      chapter: 1,
      kind: "ask",
      question: "Q?",
      answer: "prior",
      followups: [{ question: "why?", answer: "" }],
      createdAt: "",
      updatedAt: "",
    };
    updateAsk.mockImplementation(
      (_id: string, updater: (prev: AskCard) => AskCard) => {
        fakeCard = updater(fakeCard);
        captured.push(fakeCard);
      },
    );

    const p = followupAndStream({
      cardId: "card-x",
      bookId: "b",
      maxChapter: 1,
      question: "why?",
      appendFollowup,
      updateAsk,
      queryBook,
      streamMinMs: 1,
      streamMaxMs: 1,
    });
    await vi.runAllTimersAsync();
    await p;

    // appendFollowup must be called with the question before streaming begins.
    expect(appendFollowup).toHaveBeenCalledWith("card-x", "why?", "");
    // Final followup answer should be the full response.
    expect(fakeCard.followups[fakeCard.followups.length - 1].answer).toBe(
      "because reasons",
    );
    expect(captured.length).toBeGreaterThan(0);
  });
});
