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
