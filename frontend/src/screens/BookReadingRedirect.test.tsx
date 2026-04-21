import { render, screen, waitFor } from "@testing-library/react";
import { describe, it, expect, afterEach, vi } from "vitest";
import { MemoryRouter, Routes, Route } from "react-router-dom";
import { BookReadingRedirect } from "./BookReadingRedirect";

const CC = {
  book_id: "christmas_carol_e6ddcd76",
  title: "Christmas Carol",
  total_chapters: 3,
  current_chapter: 2,
  ready_for_query: true,
};

describe("BookReadingRedirect", () => {
  const originalFetch = globalThis.fetch;
  afterEach(() => {
    globalThis.fetch = originalFetch;
  });

  it("fetches /books and <Navigate>s to /books/:bookId/read/:current_chapter", async () => {
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve([CC]),
    }) as unknown as typeof fetch;

    render(
      <MemoryRouter initialEntries={["/books/christmas_carol_e6ddcd76/read"]}>
        <Routes>
          <Route
            path="/books/:bookId/read"
            element={<BookReadingRedirect />}
          />
          <Route
            path="/books/:bookId/read/:chapterNum"
            element={<div data-testid="landed">LANDED</div>}
          />
        </Routes>
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByTestId("landed")).toBeInTheDocument();
    });
  });

  it("shows a loading state before the books call resolves", () => {
    globalThis.fetch = vi.fn(() => new Promise(() => {})) as unknown as typeof fetch;
    render(
      <MemoryRouter initialEntries={["/books/christmas_carol_e6ddcd76/read"]}>
        <Routes>
          <Route path="/books/:bookId/read" element={<BookReadingRedirect />} />
        </Routes>
      </MemoryRouter>
    );
    expect(screen.getByText(/opening/i)).toBeInTheDocument();
  });

  it("shows an error when the book is not found in /books", async () => {
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve([]),
    }) as unknown as typeof fetch;
    render(
      <MemoryRouter initialEntries={["/books/missing_book/read"]}>
        <Routes>
          <Route path="/books/:bookId/read" element={<BookReadingRedirect />} />
        </Routes>
      </MemoryRouter>
    );
    await waitFor(() => {
      expect(screen.getByRole("alert")).toBeInTheDocument();
    });
  });
});
