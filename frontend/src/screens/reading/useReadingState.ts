import { useEffect, useState } from "react";
import type { Book, Chapter, ChapterSummary } from "../../lib/api";

export type BodyState =
  | { kind: "idle" }
  | { kind: "loading" }
  | { kind: "error"; message: string }
  | { kind: "ok"; chapter: Chapter };

type Deps = {
  bookId: string;
  n: number;
  fetchBooks: () => Promise<Book[]>;
  fetchChapters: (bookId: string) => Promise<ChapterSummary[]>;
  fetchChapter: (bookId: string, n: number) => Promise<Chapter>;
  setProgress: (
    bookId: string,
    current_chapter: number,
  ) => Promise<{ current_chapter: number }>;
  onMarkAsRead?: (nextChapter: number) => void;
};

// Owns the "what book + chapter is the user reading" state for ReadingScreen:
// book fetch, chapter list, chapter body (idle/loading/error/ok), and the
// mark-as-read progression. Deps are injected so this hook tests cleanly.
export function useReadingState({
  bookId,
  n,
  fetchBooks,
  fetchChapters,
  fetchChapter,
  setProgress,
  onMarkAsRead,
}: Deps) {
  const [book, setBook] = useState<Book | null>(null);
  const [chapterList, setChapterList] = useState<ChapterSummary[] | null>(null);
  const [body, setBody] = useState<BodyState>({ kind: "idle" });

  useEffect(() => {
    let cancelled = false;
    Promise.all([fetchBooks(), fetchChapters(bookId)])
      .then(([books, chapters]) => {
        if (cancelled) return;
        setBook(books.find((b) => b.book_id === bookId) ?? null);
        setChapterList(chapters);
      })
      .catch((err: unknown) => {
        // One-shot load, not a poll loop — log and leave the sidebar empty.
        console.error("reading sidebar load failed", err);
      });
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [bookId]);

  useEffect(() => {
    if (!book) return;
    if (n > book.current_chapter + 1) {
      setBody({ kind: "idle" });
      return;
    }
    let cancelled = false;
    setBody({ kind: "loading" });
    fetchChapter(bookId, n)
      .then((chapter) => {
        if (cancelled) return;
        setBody({ kind: "ok", chapter });
      })
      .catch((err: unknown) => {
        if (cancelled) return;
        setBody({
          kind: "error",
          message: err instanceof Error ? err.message : String(err),
        });
      });
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [bookId, n, book?.current_chapter]);

  async function handleMarkAsRead() {
    if (!book) return;
    const next = n + 1;
    await setProgress(bookId, next);
    const fresh = await fetchBooks();
    setBook(fresh.find((b) => b.book_id === bookId) ?? null);
    onMarkAsRead?.(next);
  }

  return { book, chapterList, body, handleMarkAsRead };
}
