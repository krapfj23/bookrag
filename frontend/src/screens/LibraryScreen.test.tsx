import { render, screen, waitFor } from "@testing-library/react";
import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { LibraryScreen } from "./LibraryScreen";

const CC = {
  book_id: "christmas_carol_e6ddcd76",
  title: "Christmas Carol",
  total_chapters: 3,
  current_chapter: 1,
  ready_for_query: true,
};

describe("LibraryScreen", () => {
  const originalFetch = globalThis.fetch;
  afterEach(() => {
    globalThis.fetch = originalFetch;
  });

  it("shows a loading state before the response arrives", () => {
    globalThis.fetch = vi.fn(() => new Promise(() => {})) as unknown as typeof fetch;
    render(<LibraryScreen />);
    expect(screen.getByText(/loading/i)).toBeInTheDocument();
  });

  it("renders one BookCard per returned book after success", async () => {
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve([CC]),
    }) as unknown as typeof fetch;

    render(<LibraryScreen />);

    await waitFor(() => {
      expect(screen.getByText("Christmas Carol")).toBeInTheDocument();
    });
    expect(screen.getByText(/of\s*3/i)).toBeInTheDocument();
  });

  it("shows an error message when the fetch fails", async () => {
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 500,
    }) as unknown as typeof fetch;

    render(<LibraryScreen />);

    await waitFor(() => {
      expect(screen.getByText(/couldn.?t load your books/i)).toBeInTheDocument();
    });
  });

  it("renders the 'Your shelf' header and NavBar", async () => {
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve([]),
    }) as unknown as typeof fetch;

    render(<LibraryScreen />);

    expect(screen.getByText(/your shelf/i)).toBeInTheDocument();
    // NavBar's three tabs
    expect(screen.getByText("Library")).toBeInTheDocument();
    expect(screen.getByText("Reading")).toBeInTheDocument();
    expect(screen.getByText("Upload")).toBeInTheDocument();
  });
});
