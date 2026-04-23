/**
 * @vitest-environment jsdom
 */
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, waitFor, act } from "@testing-library/react";
import { MemoryRouter, Routes, Route } from "react-router-dom";
import { ReadingScreen } from "./ReadingScreen";
import * as api from "../lib/api";

function mockFetch(response: Record<string, unknown>) {
  return vi.fn(async () =>
    new Response(JSON.stringify(response), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    }),
  ) as typeof fetch;
}

const CH = {
  num: 1,
  title: "Marley's Ghost",
  paragraphs: ["Alpha. Bravo.", "Charlie."],
  paragraphs_anchored: [
    {
      paragraph_idx: 1,
      sentences: [
        { sid: "p1.s1", text: "Alpha." },
        { sid: "p1.s2", text: "Bravo." },
      ],
    },
    {
      paragraph_idx: 2,
      sentences: [{ sid: "p2.s1", text: "Charlie." }],
    },
  ],
  anchors_fallback: false,
  has_prev: false,
  has_next: true,
  total_chapters: 5,
};

describe("ReadingScreen — slice R1", () => {
  const realFetch = global.fetch;
  beforeEach(() => {
    window.localStorage.clear();
    global.fetch = mockFetch(CH);
  });
  afterEach(() => {
    global.fetch = realFetch;
  });

  function renderAt(path = "/books/carol/read/1") {
    return render(
      <MemoryRouter initialEntries={[path]}>
        <Routes>
          <Route
            path="/books/:bookId/read/:chapterNum"
            element={<ReadingScreen />}
          />
        </Routes>
      </MemoryRouter>,
    );
  }

  it("renders a two-page spread with data-sid sentences", async () => {
    renderAt();
    await waitFor(() =>
      expect(screen.getByTestId("book-spread")).toBeInTheDocument(),
    );
    expect(document.querySelector('[data-sid="p1.s1"]')).not.toBeNull();
    expect(document.querySelector('[data-sid="p2.s1"]')).not.toBeNull();
  });

  it("ArrowRight at last spread navigates forward without crash (no crash)", async () => {
    renderAt();
    await waitFor(() => screen.getByTestId("book-spread"));
    await act(async () => {
      window.dispatchEvent(new KeyboardEvent("keydown", { key: "ArrowRight" }));
    });
    // After navigation to ch2 the spread should appear again (mock returns CH data).
    await waitFor(() => screen.getByTestId("book-spread"));
    expect(screen.getByTestId("book-spread")).toBeInTheDocument();
  });

  it("initial cursor is p1.s1 when storage empty", async () => {
    renderAt();
    await waitFor(() => screen.getByTestId("book-spread"));
    // The first sentence should be un-fogged (opacity:1); later sentences fogged.
    const first = document.querySelector('[data-sid="p1.s1"]') as HTMLElement;
    expect(first.getAttribute("style") ?? "").toMatch(/opacity:\s*1/);
  });
});

function renderAtR2(path: string) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route
          path="/books/:bookId/read/:chapterNum"
          element={<ReadingScreen />}
        />
      </Routes>
    </MemoryRouter>,
  );
}

describe("ReadingScreen (R2 integration)", () => {
  beforeEach(() => {
    window.localStorage.clear();
    vi.spyOn(api, "fetchChapter").mockResolvedValue({
      num: 1,
      title: "C1",
      total_chapters: 1,
      has_prev: false,
      has_next: false,
      paragraphs: ["x"],
      paragraphs_anchored: [
        {
          paragraph_idx: 1,
          sentences: [
            { sid: "p1.s1", text: "Alpha sentence here." },
            { sid: "p1.s2", text: "Bravo sentence here." },
          ],
        },
      ],
      anchors_fallback: false,
    });
  });

  it("renders MarginColumn with S1 empty when no cards", async () => {
    renderAtR2("/books/carol/read/1");
    await waitFor(() =>
      expect(screen.getByTestId("margin-column")).toBeInTheDocument(),
    );
    expect(screen.getByTestId("s1-empty-card")).toBeInTheDocument();
  });
});

// T4 tests use MemoryRouter + location inspection instead of mocking useNavigate
// (vi.mock hoisting makes factory-level mocks incompatible with per-test variables).
describe("ReadingScreen — slice R1b T4 chapter auto-advance", () => {
  beforeEach(() => {
    window.localStorage.clear();
    vi.spyOn(api, "fetchChapter").mockResolvedValue({
      num: 1,
      title: "C1",
      total_chapters: 3,
      has_prev: false,
      has_next: true,
      paragraphs: ["A."],
      paragraphs_anchored: [
        { paragraph_idx: 1, sentences: [{ sid: "p1.s1", text: "A." }] },
      ],
      anchors_fallback: false,
    });
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  // Helper that renders ReadingScreen in a MemoryRouter and exposes a ref to
  // the router's current location so we can assert navigation.
  function renderT4WithLocation(path = "/books/carol/read/1") {
    let locationRef = { pathname: path, state: null as unknown };
    function LocationCapture() {
      const loc = (window as unknown as { __testLocation?: { pathname: string; state: unknown } }).__testLocation;
      if (loc) {
        locationRef.pathname = loc.pathname;
        locationRef.state = loc.state;
      }
      return null;
    }
    // We render inside a MemoryRouter so navigate() updates the in-memory URL.
    // The ReadingScreen uses useNavigate internally — MemoryRouter wires it up.
    const { unmount } = render(
      <MemoryRouter initialEntries={[path]}>
        <Routes>
          <Route path="/books/:bookId/read/:chapterNum" element={<ReadingScreen />} />
          <Route path="*" element={<span data-testid="navigated-away" />} />
        </Routes>
      </MemoryRouter>,
    );
    return { locationRef, unmount };
  }

  it("ArrowRight on last spread of chapter N < total navigates to chapter N+1", async () => {
    renderT4WithLocation("/books/carol/read/1");
    await waitFor(() => screen.getByTestId("book-spread"));

    await act(async () => {
      window.dispatchEvent(new KeyboardEvent("keydown", { key: "ArrowRight" }));
    });

    // After navigation the route changes — book-spread for ch2 should render.
    // fetchChapter will be called again for ch2 (still mocked).
    await waitFor(() => {
      // The component should have navigated; since ch2 mock returns ch1 data,
      // the spread still renders. We check the navigate was attempted by
      // verifying the new chapter's fetch is called.
      expect(api.fetchChapter).toHaveBeenCalledWith("carol", 2);
    });
  });

  it("ArrowRight on last spread of last chapter (N = total) is a no-op", async () => {
    vi.spyOn(api, "fetchChapter").mockResolvedValue({
      num: 3,
      title: "C3",
      total_chapters: 3,
      has_prev: true,
      has_next: false,
      paragraphs: ["Z."],
      paragraphs_anchored: [
        { paragraph_idx: 1, sentences: [{ sid: "p1.s1", text: "Z." }] },
      ],
      anchors_fallback: false,
    });
    renderT4WithLocation("/books/carol/read/3");
    await waitFor(() => screen.getByTestId("book-spread"));
    const callsBefore = (api.fetchChapter as ReturnType<typeof vi.fn>).mock.calls.length;

    await act(async () => {
      window.dispatchEvent(new KeyboardEvent("keydown", { key: "ArrowRight" }));
    });

    // No additional fetch call = no navigation to ch4.
    expect((api.fetchChapter as ReturnType<typeof vi.fn>).mock.calls.length).toBe(callsBefore);
  });

  it("ArrowLeft on spread 0 of chapter N > 1 navigates to chapter N-1", async () => {
    vi.spyOn(api, "fetchChapter").mockResolvedValue({
      num: 2,
      title: "C2",
      total_chapters: 3,
      has_prev: true,
      has_next: true,
      paragraphs: ["B."],
      paragraphs_anchored: [
        { paragraph_idx: 1, sentences: [{ sid: "p1.s1", text: "B." }] },
      ],
      anchors_fallback: false,
    });
    renderT4WithLocation("/books/carol/read/2");
    await waitFor(() => screen.getByTestId("book-spread"));

    await act(async () => {
      window.dispatchEvent(new KeyboardEvent("keydown", { key: "ArrowLeft" }));
    });

    await waitFor(() => {
      expect(api.fetchChapter).toHaveBeenCalledWith("carol", 1);
    });
  });

  it("ArrowLeft on spread 0 of chapter 1 is a no-op", async () => {
    renderT4WithLocation("/books/carol/read/1");
    await waitFor(() => screen.getByTestId("book-spread"));
    const callsBefore = (api.fetchChapter as ReturnType<typeof vi.fn>).mock.calls.length;

    await act(async () => {
      window.dispatchEvent(new KeyboardEvent("keydown", { key: "ArrowLeft" }));
    });

    // No fetch for ch0.
    expect((api.fetchChapter as ReturnType<typeof vi.fn>).mock.calls.length).toBe(callsBefore);
    expect(api.fetchChapter).not.toHaveBeenCalledWith("carol", 0);
  });
});

describe("ReadingScreen — slice R1b T2 visibleSids current-spread-only", () => {
  beforeEach(() => {
    window.localStorage.clear();
    // Chapter has 3 sids spread across 2 mock spreads.
    vi.spyOn(api, "fetchChapter").mockResolvedValue({
      num: 1,
      title: "C1",
      total_chapters: 3,
      has_prev: false,
      has_next: true,
      paragraphs: ["A.", "B.", "C."],
      paragraphs_anchored: [
        { paragraph_idx: 1, sentences: [{ sid: "p1.s1", text: "A." }] },
        { paragraph_idx: 2, sentences: [{ sid: "p2.s1", text: "B." }] },
        { paragraph_idx: 3, sentences: [{ sid: "p3.s1", text: "C." }] },
      ],
      anchors_fallback: false,
    });
  });

  it("only cards anchored to current spread sids render (not prior-spread cards)", async () => {
    // Seed cards: one on each of 3 sids.
    const store = {
      version: 1,
      cards: [
        {
          id: "card-s0",
          bookId: "carol",
          anchor: "p1.s1",
          quote: "A.",
          chapter: 1,
          kind: "ask",
          question: "Q1",
          answer: "Answer-spread0",
          followups: [],
          createdAt: new Date().toISOString(),
          updatedAt: new Date().toISOString(),
        },
        {
          id: "card-s1a",
          bookId: "carol",
          anchor: "p2.s1",
          quote: "B.",
          chapter: 1,
          kind: "ask",
          question: "Q2",
          answer: "Answer-spread1a",
          followups: [],
          createdAt: new Date().toISOString(),
          updatedAt: new Date().toISOString(),
        },
        {
          id: "card-s1b",
          bookId: "carol",
          anchor: "p3.s1",
          quote: "C.",
          chapter: 1,
          kind: "ask",
          question: "Q3",
          answer: "Answer-spread1b",
          followups: [],
          createdAt: new Date().toISOString(),
          updatedAt: new Date().toISOString(),
        },
      ],
    };
    window.localStorage.setItem("bookrag.cards.carol", JSON.stringify(store));

    // Mock paginate to return 2 spreads.
    const { paginate } = await import("../lib/reader/paginator");
    const paginateSpy = vi.spyOn(await import("../lib/reader/paginator"), "paginate").mockReturnValue([
      {
        index: 0,
        left: [{ paragraph_idx: 1, sentences: [{ sid: "p1.s1", text: "A." }] }],
        right: [],
        firstSid: "p1.s1",
        lastSid: "p1.s1",
      },
      {
        index: 1,
        left: [{ paragraph_idx: 2, sentences: [{ sid: "p2.s1", text: "B." }] }],
        right: [{ paragraph_idx: 3, sentences: [{ sid: "p3.s1", text: "C." }] }],
        firstSid: "p2.s1",
        lastSid: "p3.s1",
      },
    ]);

    const { unmount } = render(
      <MemoryRouter initialEntries={["/books/carol/read/1"]}>
        <Routes>
          <Route path="/books/:bookId/read/:chapterNum" element={<ReadingScreen />} />
        </Routes>
      </MemoryRouter>,
    );

    await waitFor(() => screen.getByTestId("book-spread"));

    // On spread 0: only card-s0 visible, not card-s1a or card-s1b.
    expect(screen.queryByText(/Answer-spread0/)).toBeInTheDocument();
    expect(screen.queryByText(/Answer-spread1a/)).not.toBeInTheDocument();
    expect(screen.queryByText(/Answer-spread1b/)).not.toBeInTheDocument();

    // Advance to spread 1.
    await act(async () => {
      window.dispatchEvent(new KeyboardEvent("keydown", { key: "ArrowRight" }));
    });

    // On spread 1: spread0 card NOT visible (not accumulated), spread1 cards visible.
    expect(screen.queryByText(/Answer-spread0/)).not.toBeInTheDocument();
    expect(screen.queryByText(/Answer-spread1a/)).toBeInTheDocument();
    expect(screen.queryByText(/Answer-spread1b/)).toBeInTheDocument();

    paginateSpy.mockRestore();
    unmount();
  });
});

describe("ReadingScreen — slice R4 reading mode integration", () => {
  beforeEach(() => {
    window.localStorage.clear();
    vi.spyOn(api, "fetchChapter").mockResolvedValue({
      num: 1,
      title: "Marley's Ghost",
      total_chapters: 5,
      has_prev: false,
      has_next: true,
      paragraphs: ["Alpha. Bravo.", "Charlie."],
      paragraphs_anchored: [
        {
          paragraph_idx: 1,
          sentences: [
            { sid: "p1.s1", text: "Alpha sentence here with more words." },
            { sid: "p1.s2", text: "Bravo sentence here with more words." },
          ],
        },
        {
          paragraph_idx: 2,
          sentences: [{ sid: "p2.s1", text: "Charlie sentence here." }],
        },
      ],
      anchors_fallback: false,
    });
  });

  function renderAtR4(path = "/books/carol/read/1") {
    return render(
      <MemoryRouter initialEntries={[path]}>
        <Routes>
          <Route
            path="/books/:bookId/read/:chapterNum"
            element={<ReadingScreen />}
          />
        </Routes>
      </MemoryRouter>,
    );
  }

  it("reader root has data-reading-mode=off by default", async () => {
    renderAtR4();
    await waitFor(() => screen.getByTestId("reading-screen"));
    const root = screen.getByTestId("reading-screen");
    expect(root.getAttribute("data-reading-mode")).toBe("off");
    expect(screen.queryByTestId("pacing-label")).not.toBeInTheDocument();
    expect(screen.queryByTestId("page-arrow-left")).not.toBeInTheDocument();
    expect(screen.queryByTestId("page-arrow-right")).not.toBeInTheDocument();
    expect(screen.queryByTestId("progress-hairline")).not.toBeInTheDocument();
    expect(screen.queryByTestId("reading-mode-legend")).not.toBeInTheDocument();
  });

  it("toggling the pill flips data-reading-mode and shows chrome when on", async () => {
    renderAtR4();
    await waitFor(() => screen.getByTestId("reading-screen"));
    const toggle = screen.getByRole("button", { name: /reading mode/i });
    await act(async () => {
      toggle.click();
    });
    const root = screen.getByTestId("reading-screen");
    expect(root.getAttribute("data-reading-mode")).toBe("on");
    expect(screen.getByTestId("pacing-label")).toBeInTheDocument();
    expect(screen.getByTestId("page-arrow-left")).toBeInTheDocument();
    expect(screen.getByTestId("page-arrow-right")).toBeInTheDocument();
    expect(screen.getByTestId("progress-hairline")).toBeInTheDocument();
    expect(screen.getByTestId("reading-mode-legend")).toBeInTheDocument();
    // Margin column is removed from the DOM when reading mode is on so the
    // book spread centers without a reserved sidebar column.
    expect(screen.queryByTestId("margin-column")).not.toBeInTheDocument();
  });

  it("toggling off from on removes chrome and restores margin visibility", async () => {
    renderAtR4();
    await waitFor(() => screen.getByTestId("reading-screen"));
    const toggle = screen.getByRole("button", { name: /reading mode/i });
    await act(async () => {
      toggle.click();
    });
    await act(async () => {
      toggle.click();
    });
    const root = screen.getByTestId("reading-screen");
    expect(root.getAttribute("data-reading-mode")).toBe("off");
    expect(screen.queryByTestId("pacing-label")).not.toBeInTheDocument();
    expect(screen.queryByTestId("reading-mode-legend")).not.toBeInTheDocument();
    const margin = screen.getByTestId("margin-column");
    expect(margin.getAttribute("aria-hidden")).not.toBe("true");
  });

  it("persists on-state across remount for same bookId", async () => {
    const { unmount } = renderAtR4();
    await waitFor(() => screen.getByTestId("reading-screen"));
    const toggle = screen.getByRole("button", { name: /reading mode/i });
    await act(async () => {
      toggle.click();
    });
    expect(
      screen.getByTestId("reading-screen").getAttribute("data-reading-mode"),
    ).toBe("on");
    unmount();
    renderAtR4();
    await waitFor(() => screen.getByTestId("reading-screen"));
    expect(
      screen.getByTestId("reading-screen").getAttribute("data-reading-mode"),
    ).toBe("on");
  });
});
