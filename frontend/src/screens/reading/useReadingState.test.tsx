import { renderHook, waitFor } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import { useReadingState } from "./useReadingState";
import type { Book, Chapter, ChapterSummary } from "../../lib/api";

const BOOK_ID = "christmas_carol_e6ddcd76";

const BOOK: Book = {
  book_id: BOOK_ID,
  title: "Christmas Carol",
  total_chapters: 3,
  current_chapter: 2,
  ready_for_query: true,
};

const CHAPTERS: ChapterSummary[] = [
  { num: 1, title: "Chapter 1", word_count: 100 },
  { num: 2, title: "Chapter 2", word_count: 100 },
  { num: 3, title: "Chapter 3", word_count: 100 },
];

const CH2: Chapter = {
  num: 2,
  title: "Chapter 2",
  paragraphs: ["p1", "p2"],
  has_prev: true,
  has_next: true,
  total_chapters: 3,
};

describe("useReadingState", () => {
  it("loads book + chapter list + chapter body on mount", async () => {
    const fetchBooks = vi.fn().mockResolvedValue([BOOK]);
    const fetchChapters = vi.fn().mockResolvedValue(CHAPTERS);
    const fetchChapter = vi.fn().mockResolvedValue(CH2);
    const setProgress = vi
      .fn()
      .mockResolvedValue({ book_id: BOOK_ID, current_chapter: 3 });

    const { result } = renderHook(() =>
      useReadingState({
        bookId: BOOK_ID,
        n: 2,
        fetchBooks,
        fetchChapters,
        fetchChapter,
        setProgress,
      }),
    );

    await waitFor(() => expect(result.current.book).not.toBeNull());
    expect(result.current.chapterList).toHaveLength(3);
    await waitFor(() => expect(result.current.body.kind).toBe("ok"));
    if (result.current.body.kind === "ok") {
      expect(result.current.body.chapter.paragraphs).toEqual(["p1", "p2"]);
    }
  });

  it("sets body to idle when n is beyond current_chapter + 1 (does not fetch)", async () => {
    const fetchBooks = vi.fn().mockResolvedValue([BOOK]);
    const fetchChapters = vi.fn().mockResolvedValue(CHAPTERS);
    const fetchChapter = vi.fn().mockResolvedValue(CH2);
    const setProgress = vi.fn();

    const { result } = renderHook(() =>
      useReadingState({
        bookId: BOOK_ID,
        n: 5,
        fetchBooks,
        fetchChapters,
        fetchChapter,
        setProgress,
      }),
    );

    await waitFor(() => expect(result.current.book).not.toBeNull());
    expect(fetchChapter).not.toHaveBeenCalled();
    expect(result.current.body.kind).toBe("idle");
  });

  it("sets body to error when fetchChapter rejects", async () => {
    const fetchBooks = vi.fn().mockResolvedValue([BOOK]);
    const fetchChapters = vi.fn().mockResolvedValue(CHAPTERS);
    const fetchChapter = vi.fn().mockRejectedValue(new Error("boom"));
    const setProgress = vi.fn();

    const { result } = renderHook(() =>
      useReadingState({
        bookId: BOOK_ID,
        n: 2,
        fetchBooks,
        fetchChapters,
        fetchChapter,
        setProgress,
      }),
    );

    await waitFor(() => expect(result.current.body.kind).toBe("error"));
    if (result.current.body.kind === "error") {
      expect(result.current.body.message).toBe("boom");
    }
  });

  it("handleMarkAsRead POSTs n+1 and refreshes the book", async () => {
    const fetchBooks = vi
      .fn()
      .mockResolvedValueOnce([BOOK])
      .mockResolvedValueOnce([{ ...BOOK, current_chapter: 3 }]);
    const fetchChapters = vi.fn().mockResolvedValue(CHAPTERS);
    const fetchChapter = vi.fn().mockResolvedValue(CH2);
    const setProgress = vi
      .fn()
      .mockResolvedValue({ book_id: BOOK_ID, current_chapter: 3 });
    const onMarkAsRead = vi.fn();

    const { result } = renderHook(() =>
      useReadingState({
        bookId: BOOK_ID,
        n: 2,
        fetchBooks,
        fetchChapters,
        fetchChapter,
        setProgress,
        onMarkAsRead,
      }),
    );
    await waitFor(() => expect(result.current.book).not.toBeNull());
    await result.current.handleMarkAsRead();
    expect(setProgress).toHaveBeenCalledWith(BOOK_ID, 3);
    expect(onMarkAsRead).toHaveBeenCalledWith(3);
  });
});
