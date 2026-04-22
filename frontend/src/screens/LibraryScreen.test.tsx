import { render, screen, waitFor } from "@testing-library/react";
import { describe, it, expect, afterEach, vi } from "vitest";
import { MemoryRouter, Routes, Route, Link } from "react-router-dom";
import userEvent from "@testing-library/user-event";
import { LibraryScreen } from "./LibraryScreen";

const CC = {
  book_id: "christmas_carol_e6ddcd76",
  title: "Christmas Carol",
  total_chapters: 3,
  current_chapter: 1,
  ready_for_query: true,
};

function renderLib() {
  return render(
    <MemoryRouter initialEntries={["/"]}>
      <LibraryScreen />
    </MemoryRouter>,
  );
}

describe("LibraryScreen", () => {
  const originalFetch = globalThis.fetch;
  afterEach(() => {
    globalThis.fetch = originalFetch;
  });

  it("shows a loading state before the response arrives", () => {
    globalThis.fetch = vi.fn(() => new Promise(() => {})) as unknown as typeof fetch;
    renderLib();
    expect(screen.getByText(/loading/i)).toBeInTheDocument();
  });

  it("renders one BookCard per returned book after success", async () => {
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve([CC]),
    }) as unknown as typeof fetch;

    renderLib();

    await waitFor(() => {
      expect(screen.getAllByText("Christmas Carol").length).toBeGreaterThanOrEqual(1);
    });
    expect(screen.getByText(/of\s*3/i)).toBeInTheDocument();
  });

  it("shows an error message when the fetch fails", async () => {
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 500,
    }) as unknown as typeof fetch;

    renderLib();

    await waitFor(() => {
      expect(screen.getByText(/couldn.?t load your books/i)).toBeInTheDocument();
    });
  });

  it("renders the 'Your shelf' header and NavBar", async () => {
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve([]),
    }) as unknown as typeof fetch;

    renderLib();

    expect(screen.getByText(/your shelf/i)).toBeInTheDocument();
    expect(screen.getByText("Library")).toBeInTheDocument();
    expect(screen.getByText("Reading")).toBeInTheDocument();
    expect(screen.getByText("Upload")).toBeInTheDocument();
  });

  it("re-fetches /books each time the user navigates back to /", async () => {
    // Uses a single <MemoryRouter> with <Link> navigation between routes so
    // the test actually exercises the effect's re-entry behavior rather than
    // forcing a remount via two separate routers.
    const fetchMock = vi
      .fn()
      .mockResolvedValue({ ok: true, json: () => Promise.resolve([]) });
    globalThis.fetch = fetchMock as unknown as typeof fetch;
    const user = userEvent.setup();

    render(
      <MemoryRouter initialEntries={["/"]}>
        <Routes>
          <Route
            path="/"
            element={
              <>
                <LibraryScreen />
                <Link to="/upload">go to upload</Link>
              </>
            }
          />
          <Route path="/upload" element={<Link to="/">back home</Link>} />
        </Routes>
      </MemoryRouter>,
    );

    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1));

    await user.click(screen.getByRole("link", { name: /go to upload/i }));
    await user.click(await screen.findByRole("link", { name: /back home/i }));

    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2));
  });
});
