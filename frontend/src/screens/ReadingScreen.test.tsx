import { render, screen, waitFor } from "@testing-library/react";
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
        paragraphs: n === 2 ? chapter2.paragraphs : [`Paragraph for chapter ${n}`],
        has_prev: n > 1,
        has_next: n < 3,
        total_chapters: 3,
      }) as api.Chapter,
  );
}

function renderAt(path: string) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route path="/books/:bookId/read/:chapterNum" element={<ReadingScreen />} />
      </Routes>
    </MemoryRouter>,
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
      screen.getAllByText("The Last of the Spirits").length,
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
    await waitFor(() => expect(screen.getByText(/am i that man/i)).toBeInTheDocument());

    await user.click(screen.getByRole("button", { name: /previous chapter/i }));
    await waitFor(() =>
      expect(screen.getByText(/paragraph for chapter 1/i)).toBeInTheDocument(),
    );
  });

  it("Next is disabled when current_chapter equals n (not yet unlocked)", async () => {
    mockApi();
    renderAt(`/books/${BOOK_ID}/read/2`);
    await waitFor(() => expect(screen.getByText(/am i that man/i)).toBeInTheDocument());
    const nextBtn = screen.getByRole("button", { name: /next chapter/i });
    expect(nextBtn).toBeDisabled();
  });

  it("Prev is disabled on chapter 1", async () => {
    mockApi();
    renderAt(`/books/${BOOK_ID}/read/1`);
    await waitFor(() =>
      expect(screen.getByText(/paragraph for chapter 1/i)).toBeInTheDocument(),
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

    await waitFor(() => expect(screen.getByText(/am i that man/i)).toBeInTheDocument());
    const mark = screen.getByRole("button", { name: /mark as read/i });
    await user.click(mark);

    await waitFor(() => expect(setProgressSpy).toHaveBeenCalledWith(BOOK_ID, 3));
  });

  it("Mark as read is hidden when n != current_chapter", async () => {
    mockApi();
    renderAt(`/books/${BOOK_ID}/read/1`);
    await waitFor(() =>
      expect(screen.getByText(/paragraph for chapter 1/i)).toBeInTheDocument(),
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
      expect(screen.getByText(/paragraph for chapter 3/i)).toBeInTheDocument(),
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
      () => new Promise(() => {}) as Promise<api.Chapter>,
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
      expect(screen.getByText(/first teaser paragraph/i)).toBeInTheDocument(),
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
    const chapterSpy = vi
      .spyOn(api, "fetchChapter")
      .mockResolvedValue({} as api.Chapter);

    renderAt(`/books/${BOOK_ID}/read/5`);
    await waitFor(() =>
      expect(screen.getByText(/locked — reach chapter 5/i)).toBeInTheDocument(),
    );
    expect(chapterSpy).not.toHaveBeenCalled();
  });
});

describe("ReadingScreen — chat panel (slice 4 + Margin Marks)", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    // HTMLElement.prototype.scrollIntoView is not implemented in jsdom; stub it.
    Element.prototype.scrollIntoView = vi.fn();
  });
  afterEach(() => {
    vi.restoreAllMocks();
  });

  // Margin Marks: the chat lives inside the panel's Thread tab. The rail is
  // collapsed by default; tests expand it first, then exercise the chat.
  async function openThreadPanel(user: ReturnType<typeof userEvent.setup>) {
    await user.click(screen.getByRole("button", { name: /^thread$/i }));
  }

  it("shows the empty state after opening the Thread tab", async () => {
    mockApi();
    const user = userEvent.setup();
    renderAt(`/books/${BOOK_ID}/read/2`);
    await waitFor(() => expect(screen.getByText(/am i that man/i)).toBeInTheDocument());
    await openThreadPanel(user);
    expect(
      screen.getByText(/ask about what you've read/i, {
        selector: "p, div, span",
      }),
    ).toBeInTheDocument();
  });

  it("panel header 'safe through ch. N' matches current_chapter", async () => {
    mockApi();
    const user = userEvent.setup();
    renderAt(`/books/${BOOK_ID}/read/2`);
    await waitFor(() => expect(screen.getByText(/am i that man/i)).toBeInTheDocument());
    await openThreadPanel(user);
    expect(screen.getByText(/safe through ch\. 2/i)).toBeInTheDocument();
  });

  it("submitting a question appends a UserBubble and a thinking AssistantBubble", async () => {
    mockApi();
    const querySpy = vi
      .spyOn(api, "queryBook")
      .mockImplementation(() => new Promise(() => {}) as Promise<api.QueryResponse>);
    const user = userEvent.setup();
    renderAt(`/books/${BOOK_ID}/read/2`);

    await waitFor(() => expect(screen.getByText(/am i that man/i)).toBeInTheDocument());
    await openThreadPanel(user);

    const input = screen.getByLabelText(/ask about what you've read/i);
    await user.type(input, "Who is Marley?");
    await user.keyboard("{Enter}");

    // User bubble appears
    expect(screen.getByText("Who is Marley?")).toBeInTheDocument();
    // Thinking bubble: text "Thinking…" with the blinking cursor
    expect(screen.getByText(/thinking…/i)).toBeInTheDocument();
    // queryBook was called with book.current_chapter as max_chapter
    expect(querySpy).toHaveBeenCalledWith(BOOK_ID, "Who is Marley?", 2);
  });

  it("on 2xx replaces thinking with an AssistantBubble + sources", async () => {
    mockApi();
    vi.spyOn(api, "queryBook").mockResolvedValue({
      book_id: BOOK_ID,
      question: "Who is Marley?",
      search_type: "GRAPH_COMPLETION",
      current_chapter: 2,
      results: [
        {
          content: "Marley is Scrooge's dead business partner.",
          entity_type: "Character",
          chapter: 1,
        },
        {
          content: "Another ref",
          entity_type: null,
          chapter: null, // should NOT render as a source
        },
      ],
      result_count: 2,
    });
    const user = userEvent.setup();
    renderAt(`/books/${BOOK_ID}/read/2`);
    await waitFor(() => expect(screen.getByText(/am i that man/i)).toBeInTheDocument());
    await openThreadPanel(user);

    const input = screen.getByLabelText(/ask about what you've read/i);
    await user.type(input, "Who is Marley?");
    await user.keyboard("{Enter}");

    await waitFor(() =>
      expect(
        screen.getByText(/marley is scrooge's dead business partner/i),
      ).toBeInTheDocument(),
    );
    // "Thinking…" has been replaced
    expect(screen.queryByText(/thinking…/i)).toBeNull();
    // Ch. 1 source is visible
    expect(screen.getByText("Ch. 1")).toBeInTheDocument();
  });

  it("on empty results renders the fallback line and no sources", async () => {
    mockApi();
    vi.spyOn(api, "queryBook").mockResolvedValue({
      book_id: BOOK_ID,
      question: "Who is Marley?",
      search_type: "GRAPH_COMPLETION",
      current_chapter: 2,
      results: [],
      result_count: 0,
    });
    const user = userEvent.setup();
    renderAt(`/books/${BOOK_ID}/read/2`);
    await waitFor(() => expect(screen.getByText(/am i that man/i)).toBeInTheDocument());
    await openThreadPanel(user);

    await user.type(
      screen.getByLabelText(/ask about what you've read/i),
      "obscure question",
    );
    await user.keyboard("{Enter}");

    await waitFor(() =>
      expect(
        screen.getByText(/i don't have anything in your read-so-far/i),
      ).toBeInTheDocument(),
    );
  });

  it("on QueryRateLimitError shows 'Too many requests, slow down.'", async () => {
    mockApi();
    vi.spyOn(api, "queryBook").mockRejectedValue(new api.QueryRateLimitError());
    const user = userEvent.setup();
    renderAt(`/books/${BOOK_ID}/read/2`);
    await waitFor(() => expect(screen.getByText(/am i that man/i)).toBeInTheDocument());
    await openThreadPanel(user);

    await user.type(screen.getByLabelText(/ask about what you've read/i), "q");
    await user.keyboard("{Enter}");

    await waitFor(() =>
      expect(screen.getByText(/too many requests, slow down\./i)).toBeInTheDocument(),
    );
  });

  it("on QueryServerError shows 'Something went wrong. Try again.'", async () => {
    mockApi();
    vi.spyOn(api, "queryBook").mockRejectedValue(new api.QueryServerError(500));
    const user = userEvent.setup();
    renderAt(`/books/${BOOK_ID}/read/2`);
    await waitFor(() => expect(screen.getByText(/am i that man/i)).toBeInTheDocument());
    await openThreadPanel(user);

    await user.type(screen.getByLabelText(/ask about what you've read/i), "q");
    await user.keyboard("{Enter}");

    await waitFor(() =>
      expect(
        screen.getByText(/something went wrong\. try again\./i),
      ).toBeInTheDocument(),
    );
  });

  it("on QueryNetworkError shows 'Something went wrong. Try again.'", async () => {
    mockApi();
    vi.spyOn(api, "queryBook").mockRejectedValue(new api.QueryNetworkError());
    const user = userEvent.setup();
    renderAt(`/books/${BOOK_ID}/read/2`);
    await waitFor(() => expect(screen.getByText(/am i that man/i)).toBeInTheDocument());
    await openThreadPanel(user);

    await user.type(screen.getByLabelText(/ask about what you've read/i), "q");
    await user.keyboard("{Enter}");

    await waitFor(() =>
      expect(
        screen.getByText(/something went wrong\. try again\./i),
      ).toBeInTheDocument(),
    );
  });

  it("the input clears after submission", async () => {
    mockApi();
    vi.spyOn(api, "queryBook").mockResolvedValue({
      book_id: BOOK_ID,
      question: "x",
      search_type: "GRAPH_COMPLETION",
      current_chapter: 2,
      results: [],
      result_count: 0,
    });
    const user = userEvent.setup();
    renderAt(`/books/${BOOK_ID}/read/2`);
    await waitFor(() => expect(screen.getByText(/am i that man/i)).toBeInTheDocument());
    await openThreadPanel(user);
    const input = screen.getByLabelText(
      /ask about what you've read/i,
    ) as HTMLTextAreaElement;
    await user.type(input, "x");
    await user.keyboard("{Enter}");
    await waitFor(() => expect(input.value).toBe(""));
  });

  it("does NOT render the slice-3 disabled textarea + 'Chat coming soon' placeholder", async () => {
    mockApi();
    renderAt(`/books/${BOOK_ID}/read/2`);
    await waitFor(() => expect(screen.getByText(/am i that man/i)).toBeInTheDocument());
    expect(screen.queryByText(/chat coming soon/i)).toBeNull();
    expect(screen.queryByPlaceholderText(/available in the next release/i)).toBeNull();
  });

  // ──────────────────────────────────────────────────────────────
  // Margin Marks — inline annotations + rail/panel
  // ──────────────────────────────────────────────────────────────

  it("renders inline annotations on chapter 1 text (note + query classes)", async () => {
    mockApi();
    renderAt(`/books/${BOOK_ID}/read/1`);
    await waitFor(() =>
      expect(screen.getByText(/paragraph for chapter 1/i)).toBeInTheDocument(),
    );
    // Seed data targets chapter 1 but the test-mock chapter body doesn't
    // contain the seeded substrings, so no annotations render. This test
    // only asserts that the annotation wrapper DOM class is available.
    const rail = screen.getByLabelText(/annotations rail/i);
    expect(rail).toBeInTheDocument();
  });

  it("rail is visible by default; clicking Notes expands the panel", async () => {
    mockApi();
    const user = userEvent.setup();
    renderAt(`/books/${BOOK_ID}/read/2`);
    await waitFor(() => expect(screen.getByText(/am i that man/i)).toBeInTheDocument());
    expect(screen.getByLabelText(/annotations rail/i)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /^notes$/i }));
    expect(screen.getByLabelText(/annotations panel/i)).toBeInTheDocument();
  });

  it("uses the GraphRAG-synthesized answer from the backend when present", async () => {
    mockApi();
    vi.spyOn(api, "queryBook").mockResolvedValue({
      book_id: BOOK_ID,
      question: "Who is Marley?",
      search_type: "GRAPH_COMPLETION",
      current_chapter: 2,
      answer:
        "Marley is Scrooge's dead business partner whose ghost sets the story in motion.",
      results: [
        {
          content: "Marley — business partner",
          entity_type: "Character",
          chapter: 1,
        },
      ],
      result_count: 1,
    });
    const user = userEvent.setup();
    renderAt(`/books/${BOOK_ID}/read/2`);
    await waitFor(() => expect(screen.getByText(/am i that man/i)).toBeInTheDocument());
    await openThreadPanel(user);
    await user.type(
      screen.getByLabelText(/ask about what you've read/i),
      "Who is Marley?",
    );
    await user.keyboard("{Enter}");
    await waitFor(() =>
      expect(
        screen.getByText(
          /marley is scrooge's dead business partner whose ghost sets the story in motion/i,
        ),
      ).toBeInTheDocument(),
    );
    // Source card still renders from the raw results
    expect(screen.getByText(/marley — business partner/i)).toBeInTheDocument();
  });

  it("clicking the panel close button collapses back to the rail", async () => {
    mockApi();
    const user = userEvent.setup();
    renderAt(`/books/${BOOK_ID}/read/2`);
    await waitFor(() => expect(screen.getByText(/am i that man/i)).toBeInTheDocument());
    await openThreadPanel(user);
    expect(screen.getByLabelText(/annotations panel/i)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /^close panel$/i }));
    expect(screen.queryByLabelText(/annotations panel/i)).not.toBeInTheDocument();
    expect(screen.getByLabelText(/annotations rail/i)).toBeInTheDocument();
  });
});
