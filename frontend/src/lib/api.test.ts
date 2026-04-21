import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { fetchBooks } from "./api";

describe("fetchBooks", () => {
  const originalFetch = globalThis.fetch;

  beforeEach(() => {
    vi.resetAllMocks();
  });
  afterEach(() => {
    globalThis.fetch = originalFetch;
  });

  it("GETs http://localhost:8000/books and returns the JSON body", async () => {
    const body = [
      {
        book_id: "christmas_carol_e6ddcd76",
        title: "Christmas Carol",
        total_chapters: 3,
        current_chapter: 1,
        ready_for_query: true,
      },
    ];
    const mockFetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve(body),
    });
    globalThis.fetch = mockFetch as unknown as typeof fetch;

    const result = await fetchBooks();

    expect(mockFetch).toHaveBeenCalledWith("http://localhost:8000/books");
    expect(result).toEqual(body);
  });

  it("throws on non-OK responses", async () => {
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 500,
    }) as unknown as typeof fetch;
    await expect(fetchBooks()).rejects.toThrow(/500/);
  });
});
