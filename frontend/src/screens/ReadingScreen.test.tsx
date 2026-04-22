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

  it("ArrowRight at last spread does nothing (no crash)", async () => {
    renderAt();
    await waitFor(() => screen.getByTestId("book-spread"));
    act(() => {
      window.dispatchEvent(new KeyboardEvent("keydown", { key: "ArrowRight" }));
      window.dispatchEvent(new KeyboardEvent("keydown", { key: "ArrowRight" }));
    });
    // Still on screen.
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
    // Margin column is aria-hidden when on.
    const margin = screen.getByTestId("margin-column");
    expect(margin.getAttribute("aria-hidden")).toBe("true");
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
