import { render, screen, waitFor } from "@testing-library/react";
import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { MemoryRouter } from "react-router-dom";
import { App } from "./App";

describe("App router", () => {
  const originalFetch = globalThis.fetch;
  beforeEach(() => {
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve([]),
    }) as unknown as typeof fetch;
  });
  afterEach(() => {
    globalThis.fetch = originalFetch;
  });

  it("renders LibraryScreen at /", () => {
    render(
      <MemoryRouter initialEntries={["/"]}>
        <App />
      </MemoryRouter>
    );
    expect(screen.getByText(/your shelf/i)).toBeInTheDocument();
  });

  it("renders UploadScreen placeholder at /upload", () => {
    render(
      <MemoryRouter initialEntries={["/upload"]}>
        <App />
      </MemoryRouter>
    );
    expect(screen.getByText(/add a book/i)).toBeInTheDocument();
  });

  it("mounts ReadingScreen at /books/:bookId/read/:chapterNum", async () => {
    // The ReadingScreen's own data fetches will fail against the stub, but
    // the route-level assertion is that the NavBar Reading tab becomes active.
    render(
      <MemoryRouter
        initialEntries={["/books/christmas_carol_e6ddcd76/read/1"]}
      >
        <App />
      </MemoryRouter>
    );
    await waitFor(() => {
      expect(screen.getByText("Reading")).toHaveAttribute("data-active", "true");
    });
  });
});
