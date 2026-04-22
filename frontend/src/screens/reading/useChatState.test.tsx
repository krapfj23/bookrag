import { renderHook, act, waitFor } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import { useChatState } from "./useChatState";
import { QueryRateLimitError, QueryNetworkError, type Book } from "../../lib/api";

const BOOK: Book = {
  book_id: "b1",
  title: "T",
  total_chapters: 3,
  current_chapter: 2,
  ready_for_query: true,
};

describe("useChatState", () => {
  it("appends user bubble + thinking bubble, then resolves to ok", async () => {
    const queryBook = vi.fn().mockResolvedValue({
      book_id: "b1",
      question: "q",
      search_type: "GRAPH_COMPLETION",
      current_chapter: 2,
      answer: "the answer",
      results: [{ content: "src", entity_type: "Character", chapter: 1 }],
      result_count: 1,
    });
    const { result } = renderHook(() =>
      useChatState({ bookId: "b1", book: BOOK, queryBook }),
    );
    act(() => result.current.setDraft("hi"));
    await act(async () => {
      await result.current.submit();
    });
    await waitFor(() => {
      const last = result.current.messages[result.current.messages.length - 1];
      expect(last.role).toBe("assistant");
      if (last.role === "assistant") {
        expect(last.status).toBe("ok");
        expect(last.text).toBe("the answer");
      }
    });
    expect(queryBook).toHaveBeenCalledWith("b1", "hi", 2);
  });

  it("renders rate-limit copy on QueryRateLimitError", async () => {
    const queryBook = vi.fn().mockRejectedValue(new QueryRateLimitError());
    const { result } = renderHook(() =>
      useChatState({ bookId: "b1", book: BOOK, queryBook }),
    );
    act(() => result.current.setDraft("x"));
    await act(async () => {
      await result.current.submit();
    });
    const last = result.current.messages[result.current.messages.length - 1];
    if (last.role === "assistant") {
      expect(last.status).toBe("error");
      expect(last.text).toMatch(/too many requests/i);
    }
  });

  it("renders generic copy on QueryNetworkError", async () => {
    const queryBook = vi.fn().mockRejectedValue(new QueryNetworkError());
    const { result } = renderHook(() =>
      useChatState({ bookId: "b1", book: BOOK, queryBook }),
    );
    act(() => result.current.setDraft("x"));
    await act(async () => {
      await result.current.submit();
    });
    const last = result.current.messages[result.current.messages.length - 1];
    if (last.role === "assistant") {
      expect(last.text).toMatch(/something went wrong/i);
    }
  });

  it("clears pending excerpt via onPendingCleared and fires onAnswered", async () => {
    const queryBook = vi.fn().mockResolvedValue({
      book_id: "b1",
      question: "q",
      search_type: "GRAPH_COMPLETION",
      current_chapter: 2,
      answer: "a",
      results: [],
      result_count: 0,
    });
    const onPendingCleared = vi.fn();
    const onAnswered = vi.fn();
    const { result } = renderHook(() =>
      useChatState({
        bookId: "b1",
        book: BOOK,
        queryBook,
        pendingExcerpt: "some text",
        onPendingCleared,
        onAnswered,
      }),
    );
    act(() => result.current.setDraft("what about it"));
    await act(async () => {
      await result.current.submit();
    });
    expect(onPendingCleared).toHaveBeenCalled();
    expect(onAnswered).toHaveBeenCalled();
    expect(queryBook).toHaveBeenCalledWith("b1", 'About "some text": what about it', 2);
  });

  it("is a no-op when draft is empty or book is null", async () => {
    const queryBook = vi.fn();
    const { result, rerender } = renderHook(
      (p: { book: Book | null }) =>
        useChatState({ bookId: "b1", book: p.book, queryBook }),
      { initialProps: { book: BOOK } },
    );
    // empty draft
    await act(async () => {
      await result.current.submit();
    });
    expect(queryBook).not.toHaveBeenCalled();
    // null book with non-empty draft
    rerender({ book: null });
    act(() => result.current.setDraft("hi"));
    await act(async () => {
      await result.current.submit();
    });
    expect(queryBook).not.toHaveBeenCalled();
  });
});
