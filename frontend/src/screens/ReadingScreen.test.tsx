import { render, screen, waitFor, act, fireEvent } from "@testing-library/react";
import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Routes, Route } from "react-router-dom";
import { ReadingScreen } from "./ReadingScreen";
import * as api from "../lib/api";

const BOOK_ID = "christmas_carol_e6ddcd76";

function mockApi({
  books = [
    {
      book_id: BOOK_ID,
      title: "Christmas Carol",
      total_chapters: 3,
      current_chapter: 2,
      ready_for_query: true,
    },
  ],
  chapters = [
    { num: 1, title: "Chapter 1", word_count: 3000 },
    { num: 2, title: "The Last of the Spirits", word_count: 2000 },
    { num: 3, title: "Chapter 3", word_count: 500 },
  ],
  chapter2 = {
    num: 2,
    title: "The Last of the Spirits",
    paragraphs: [
      "Am I that man who lay upon the bed?",
      "The finger pointed from the grave to him.",
    ],
    has_prev: true,
    has_next: true,
    total_chapters: 3,
  },
}: Partial<{
  books: api.Book[];
  chapters: api.ChapterSummary[];
  chapter2: api.Chapter;
}> = {}) {
  vi.spyOn(api, "fetchBooks").mockResolvedValue(books);
  vi.spyOn(api, "fetchChapters").mockResolvedValue(chapters);
  vi.spyOn(api, "fetchChapter").mockImplementation(
    async (_id, n) =>
      ({
        num: n,
        title: n === 2 ? "The Last of the Spirits" : `Chapter ${n}`,
        paragraphs:
          n === 2
            ? chapter2.paragraphs
            : [`Paragraph for chapter ${n}`],
        has_prev: n > 1,
        has_next: n < 3,
        total_chapters: 3,
      }) as api.Chapter
  );
}

function renderAt(path: string) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route path="/books/:bookId/read/:chapterNum" element={<ReadingScreen />} />
      </Routes>
    </MemoryRouter>
  );
}

describe("ReadingScreen", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("renders the book title, chapter list, and current-chapter body", async () => {
    mockApi();
    renderAt(`/books/${BOOK_ID}/read/2`);

    await waitFor(() => {
      expect(screen.getAllByText("Christmas Carol").length).toBeGreaterThanOrEqual(1);
    });
    expect(
      screen.getAllByText("The Last of the Spirits").length
    ).toBeGreaterThanOrEqual(1);
    expect(screen.getByText(/am i that man/i)).toBeInTheDocument();
    expect(screen.getByText(/finger pointed/i)).toBeInTheDocument();
  });

  it("renders one <p> per paragraph in the response", async () => {
    mockApi();
    const { container } = renderAt(`/books/${BOOK_ID}/read/2`);
    await waitFor(() => {
      expect(container.querySelectorAll("article p").length).toBe(2);
    });
  });

  it("clicking prev/next buttons navigates", async () => {
    mockApi();
    const user = userEvent.setup();
    renderAt(`/books/${BOOK_ID}/read/2`);
    await waitFor(() =>
      expect(screen.getByText(/am i that man/i)).toBeInTheDocument()
    );

    await user.click(screen.getByRole("button", { name: /previous chapter/i }));
    await waitFor(() =>
      expect(screen.getByText(/paragraph for chapter 1/i)).toBeInTheDocument()
    );
  });

  it("Next is disabled when current_chapter equals n (not yet unlocked)", async () => {
    mockApi();
    renderAt(`/books/${BOOK_ID}/read/2`);
    await waitFor(() =>
      expect(screen.getByText(/am i that man/i)).toBeInTheDocument()
    );
    const nextBtn = screen.getByRole("button", { name: /next chapter/i });
    expect(nextBtn).toBeDisabled();
  });

  it("Prev is disabled on chapter 1", async () => {
    mockApi();
    renderAt(`/books/${BOOK_ID}/read/1`);
    await waitFor(() =>
      expect(screen.getByText(/paragraph for chapter 1/i)).toBeInTheDocument()
    );
    const prevBtn = screen.getByRole("button", { name: /previous chapter/i });
    expect(prevBtn).toBeDisabled();
  });

  it("Mark as read POSTs {current_chapter: n+1} when n == current_chapter", async () => {
    mockApi();
    const setProgressSpy = vi
      .spyOn(api, "setProgress")
      .mockResolvedValue({ book_id: BOOK_ID, current_chapter: 3 });
    const user = userEvent.setup();
    renderAt(`/books/${BOOK_ID}/read/2`);

    await waitFor(() =>
      expect(screen.getByText(/am i that man/i)).toBeInTheDocument()
    );
    const mark = screen.getByRole("button", { name: /mark as read/i });
    await user.click(mark);

    await waitFor(() =>
      expect(setProgressSpy).toHaveBeenCalledWith(BOOK_ID, 3)
    );
  });

  it("Mark as read is hidden when n != current_chapter", async () => {
    mockApi();
    renderAt(`/books/${BOOK_ID}/read/1`);
    await waitFor(() =>
      expect(screen.getByText(/paragraph for chapter 1/i)).toBeInTheDocument()
    );
    expect(screen.queryByRole("button", { name: /mark as read/i })).toBeNull();
  });

  it("Mark as read is hidden when n == total_chapters", async () => {
    mockApi({
      books: [
        {
          book_id: BOOK_ID,
          title: "Christmas Carol",
          total_chapters: 3,
          current_chapter: 3,
          ready_for_query: true,
        },
      ],
    });
    renderAt(`/books/${BOOK_ID}/read/3`);
    await waitFor(() =>
      expect(screen.getByText(/paragraph for chapter 3/i)).toBeInTheDocument()
    );
    expect(screen.queryByRole("button", { name: /mark as read/i })).toBeNull();
  });

  it("shows a loading state while the chapter body is pending", async () => {
    vi.spyOn(api, "fetchBooks").mockResolvedValue([
      {
        book_id: BOOK_ID,
        title: "Christmas Carol",
        total_chapters: 3,
        current_chapter: 2,
        ready_for_query: true,
      },
    ]);
    vi.spyOn(api, "fetchChapters").mockResolvedValue([
      { num: 1, title: "Chapter 1", word_count: 100 },
      { num: 2, title: "The Last of the Spirits", word_count: 100 },
      { num: 3, title: "Chapter 3", word_count: 100 },
    ]);
    // Never-resolving promise for the chapter body
    vi.spyOn(api, "fetchChapter").mockImplementation(
      () => new Promise(() => {}) as Promise<api.Chapter>
    );

    renderAt(`/books/${BOOK_ID}/read/2`);
    await waitFor(() => {
      expect(screen.getAllByText("Christmas Carol").length).toBeGreaterThanOrEqual(1);
    });
    expect(screen.getByText(/loading chapter/i)).toBeInTheDocument();
  });

  it("renders a teaser (first paragraph + ProgressiveBlur) when n == current_chapter + 1", async () => {
    // current_chapter = 2, we render chapter 3 → teaser mode
    vi.spyOn(api, "fetchBooks").mockResolvedValue([
      {
        book_id: BOOK_ID,
        title: "Christmas Carol",
        total_chapters: 5,
        current_chapter: 2,
        ready_for_query: true,
      },
    ]);
    vi.spyOn(api, "fetchChapters").mockResolvedValue([
      { num: 1, title: "Chapter 1", word_count: 100 },
      { num: 2, title: "Chapter 2", word_count: 100 },
      { num: 3, title: "Chapter 3", word_count: 100 },
      { num: 4, title: "Chapter 4", word_count: 100 },
      { num: 5, title: "Chapter 5", word_count: 100 },
    ]);
    vi.spyOn(api, "fetchChapter").mockResolvedValue({
      num: 3,
      title: "Chapter 3",
      paragraphs: ["First teaser paragraph.", "Hidden paragraph."],
      has_prev: true,
      has_next: true,
      total_chapters: 5,
    });

    const { container } = renderAt(`/books/${BOOK_ID}/read/3`);
    await waitFor(() =>
      expect(screen.getByText(/first teaser paragraph/i)).toBeInTheDocument()
    );
    // Only one <p> in the article, not two
    expect(container.querySelectorAll("article p").length).toBe(1);
    // Progressive blur CTA is present
    expect(screen.getByText(/advance to reveal/i)).toBeInTheDocument();
  });

  it("renders LockState chapterLock and does NOT fetch when n > current_chapter + 1", async () => {
    vi.spyOn(api, "fetchBooks").mockResolvedValue([
      {
        book_id: BOOK_ID,
        title: "Christmas Carol",
        total_chapters: 5,
        current_chapter: 2,
        ready_for_query: true,
      },
    ]);
    vi.spyOn(api, "fetchChapters").mockResolvedValue([
      { num: 1, title: "Chapter 1", word_count: 100 },
      { num: 2, title: "Chapter 2", word_count: 100 },
      { num: 3, title: "Chapter 3", word_count: 100 },
      { num: 4, title: "Chapter 4", word_count: 100 },
      { num: 5, title: "Chapter 5", word_count: 100 },
    ]);
    const chapterSpy = vi.spyOn(api, "fetchChapter").mockResolvedValue(
      {} as api.Chapter
    );

    renderAt(`/books/${BOOK_ID}/read/5`);
    await waitFor(() =>
      expect(screen.getByText(/locked — reach chapter 5/i)).toBeInTheDocument()
    );
    expect(chapterSpy).not.toHaveBeenCalled();
  });
});
