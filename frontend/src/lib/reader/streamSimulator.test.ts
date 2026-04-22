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
