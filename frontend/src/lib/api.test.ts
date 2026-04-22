import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import {
  fetchBooks,
  uploadBook,
  fetchStatus,
  fetchChapters,
  fetchChapter,
  setProgress,
  fetchWithTimeout,
  NetworkError,
  UploadError,
  type PipelineState,
  type Chapter,
  type ChapterSummary,
} from "./api";

describe("BASE_URL configuration", () => {
  const originalFetch = globalThis.fetch;
  afterEach(() => {
    globalThis.fetch = originalFetch;
    vi.unstubAllEnvs();
    vi.resetModules();
  });

  it("uses VITE_API_BASE_URL when set", async () => {
    vi.stubEnv("VITE_API_BASE_URL", "https://api.example.com");
    vi.resetModules();
    const freshApi = await import("./api");
    const fetchSpy = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValue(new Response(JSON.stringify([]), { status: 200 }));
    await freshApi.fetchBooks();
    expect(fetchSpy).toHaveBeenCalledWith(
      "https://api.example.com/books",
      expect.anything(),
    );
  });

  it("falls back to http://localhost:8000 when VITE_API_BASE_URL is unset", async () => {
    // Explicit undefined stub simulates the var being absent from .env
    vi.stubEnv("VITE_API_BASE_URL", undefined as unknown as string);
    vi.resetModules();
    const freshApi = await import("./api");
    const fetchSpy = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValue(new Response(JSON.stringify([]), { status: 200 }));
    await freshApi.fetchBooks();
    expect(fetchSpy).toHaveBeenCalledWith(
      "http://localhost:8000/books",
      expect.anything(),
    );
  });
});

describe("fetchWithTimeout", () => {
  const originalFetch = globalThis.fetch;
  afterEach(() => {
    globalThis.fetch = originalFetch;
    vi.useRealTimers();
  });

  it("aborts and throws NetworkError after timeoutMs", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn((_url, init) => {
        const signal = (init as RequestInit | undefined)?.signal;
        return new Promise<Response>((_resolve, reject) => {
          if (signal) {
            signal.addEventListener("abort", () => {
              const err = new Error("aborted");
              err.name = "AbortError";
              reject(err);
            });
          }
        });
      }),
    );
    vi.useFakeTimers();
    const p = fetchWithTimeout("http://x/y", {}, 100);
    // Attach a rejection handler synchronously so the runtime never sees
    // it as an unhandled rejection.
    const captured = p.catch((e) => e);
    await vi.advanceTimersByTimeAsync(101);
    await expect(captured).resolves.toBeInstanceOf(NetworkError);
  });
});

describe("fetchBooks", () => {
  const originalFetch = globalThis.fetch;
  beforeEach(() => vi.resetAllMocks());
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
    expect(mockFetch).toHaveBeenCalledWith(
      "http://localhost:8000/books",
      expect.anything(),
    );
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

describe("uploadBook", () => {
  const originalFetch = globalThis.fetch;
  afterEach(() => {
    globalThis.fetch = originalFetch;
  });

  function makeFile(name = "a-christmas-carol.epub"): File {
    return new File([new Uint8Array([0x50, 0x4b, 0x03, 0x04])], name, {
      type: "application/epub+zip",
    });
  }

  it("POSTs multipart/form-data to /books/upload and returns the body", async () => {
    const body = { book_id: "a_christmas_carol_a1b2c3d4", message: "Pipeline started" };
    const mockFetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: () => Promise.resolve(body),
    });
    globalThis.fetch = mockFetch as unknown as typeof fetch;

    const result = await uploadBook(makeFile());

    expect(mockFetch).toHaveBeenCalledTimes(1);
    const [url, init] = mockFetch.mock.calls[0];
    expect(url).toBe("http://localhost:8000/books/upload");
    expect(init.method).toBe("POST");
    expect(init.body).toBeInstanceOf(FormData);
    const form = init.body as FormData;
    expect(form.get("file")).toBeInstanceOf(File);
    expect((form.get("file") as File).name).toBe("a-christmas-carol.epub");
    expect(result).toEqual(body);
  });

  it("maps 400 to 'Only .epub files are accepted'", async () => {
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 400,
      json: () => Promise.resolve({ detail: "Only .epub files are accepted" }),
    }) as unknown as typeof fetch;

    await expect(uploadBook(makeFile("foo.txt"))).rejects.toBeInstanceOf(UploadError);
    try {
      await uploadBook(makeFile("foo.txt"));
    } catch (err) {
      expect(err).toBeInstanceOf(UploadError);
      expect((err as UploadError).status).toBe(400);
      expect((err as UploadError).message).toBe("Only .epub files are accepted");
    }
  });

  it("maps 413 to 'File too large (max 500 MB)'", async () => {
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 413,
      json: () => Promise.resolve({ detail: "too big" }),
    }) as unknown as typeof fetch;

    try {
      await uploadBook(makeFile());
    } catch (err) {
      expect(err).toBeInstanceOf(UploadError);
      expect((err as UploadError).status).toBe(413);
      expect((err as UploadError).message).toBe("File too large (max 500 MB)");
    }
  });

  it("maps 429 to 'Too many pipelines running, try again later'", async () => {
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 429,
      json: () => Promise.resolve({ detail: "5/5 running" }),
    }) as unknown as typeof fetch;

    try {
      await uploadBook(makeFile());
    } catch (err) {
      expect((err as UploadError).message).toBe(
        "Too many pipelines running, try again later",
      );
    }
  });

  it("falls back to backend detail text on other non-2xx", async () => {
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 500,
      json: () => Promise.resolve({ detail: "Failed to save uploaded file" }),
    }) as unknown as typeof fetch;

    try {
      await uploadBook(makeFile());
    } catch (err) {
      expect((err as UploadError).status).toBe(500);
      expect((err as UploadError).message).toBe("Failed to save uploaded file");
    }
  });

  it("uses a generic message when JSON parsing fails", async () => {
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 502,
      json: () => Promise.reject(new Error("not json")),
    }) as unknown as typeof fetch;

    try {
      await uploadBook(makeFile());
    } catch (err) {
      expect((err as UploadError).status).toBe(502);
      expect((err as UploadError).message).toMatch(/upload failed/i);
    }
  });
});

describe("fetchStatus", () => {
  const originalFetch = globalThis.fetch;
  afterEach(() => {
    globalThis.fetch = originalFetch;
  });

  it("GETs /books/{id}/status and returns PipelineState", async () => {
    const state: PipelineState = {
      book_id: "a_christmas_carol_a1b2c3d4",
      status: "processing",
      stages: {
        parse_epub: { status: "complete", duration_seconds: 0.4 },
        run_booknlp: { status: "running" },
        resolve_coref: { status: "pending" },
        discover_ontology: { status: "pending" },
        review_ontology: { status: "pending" },
        run_cognee_batches: { status: "pending" },
        validate: { status: "pending" },
      },
      current_batch: null,
      total_batches: null,
      ready_for_query: false,
    };
    const mockFetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve(state),
    });
    globalThis.fetch = mockFetch as unknown as typeof fetch;

    const result = await fetchStatus("a_christmas_carol_a1b2c3d4");

    expect(mockFetch).toHaveBeenCalledWith(
      "http://localhost:8000/books/a_christmas_carol_a1b2c3d4/status",
      expect.anything(),
    );
    expect(result).toEqual(state);
  });

  it("throws on non-OK responses", async () => {
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 404,
    }) as unknown as typeof fetch;
    await expect(fetchStatus("missing_book")).rejects.toThrow(/404/);
  });
});

describe("fetchChapters", () => {
  const originalFetch = globalThis.fetch;
  afterEach(() => {
    globalThis.fetch = originalFetch;
  });

  it("GETs /books/{id}/chapters and returns the JSON array", async () => {
    const body: ChapterSummary[] = [
      { num: 1, title: "Chapter 1", word_count: 3000 },
      { num: 2, title: "The Last of the Spirits", word_count: 2000 },
    ];
    const mockFetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve(body),
    });
    globalThis.fetch = mockFetch as unknown as typeof fetch;
    const result = await fetchChapters("christmas_carol_e6ddcd76");
    expect(mockFetch).toHaveBeenCalledWith(
      "http://localhost:8000/books/christmas_carol_e6ddcd76/chapters",
      expect.anything(),
    );
    expect(result).toEqual(body);
  });

  it("throws on 404", async () => {
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 404,
    }) as unknown as typeof fetch;
    await expect(fetchChapters("missing")).rejects.toThrow(/404/);
  });
});

describe("fetchChapter", () => {
  const originalFetch = globalThis.fetch;
  afterEach(() => {
    globalThis.fetch = originalFetch;
  });

  it("GETs /books/{id}/chapters/{n} and returns Chapter", async () => {
    const body: Chapter = {
      num: 2,
      title: "The Last of the Spirits",
      paragraphs: ["Am I that man who lay upon the bed?", "The finger pointed..."],
      has_prev: true,
      has_next: true,
      total_chapters: 3,
    };
    const mockFetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve(body),
    });
    globalThis.fetch = mockFetch as unknown as typeof fetch;
    const result = await fetchChapter("christmas_carol_e6ddcd76", 2);
    expect(mockFetch).toHaveBeenCalledWith(
      "http://localhost:8000/books/christmas_carol_e6ddcd76/chapters/2",
      expect.anything(),
    );
    expect(result).toEqual(body);
  });

  it("throws on 404", async () => {
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 404,
    }) as unknown as typeof fetch;
    await expect(fetchChapter("bk", 99)).rejects.toThrow(/404/);
  });
});

describe("setProgress", () => {
  const originalFetch = globalThis.fetch;
  afterEach(() => {
    globalThis.fetch = originalFetch;
  });

  it("POSTs {current_chapter: n} to /books/{id}/progress", async () => {
    const mockFetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ book_id: "bk", current_chapter: 3 }),
    });
    globalThis.fetch = mockFetch as unknown as typeof fetch;
    const result = await setProgress("bk", 3);
    expect(mockFetch).toHaveBeenCalledTimes(1);
    const [url, init] = mockFetch.mock.calls[0];
    expect(url).toBe("http://localhost:8000/books/bk/progress");
    expect(init.method).toBe("POST");
    expect(init.headers).toMatchObject({ "Content-Type": "application/json" });
    expect(init.body).toBe(JSON.stringify({ current_chapter: 3 }));
    expect(result).toEqual({ book_id: "bk", current_chapter: 3 });
  });

  it("throws on non-2xx", async () => {
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 400,
    }) as unknown as typeof fetch;
    await expect(setProgress("bk", 0)).rejects.toThrow(/400/);
  });
});

import {
  queryBook,
  QueryError,
  QueryRateLimitError,
  QueryServerError,
  QueryNetworkError,
  type QueryResponse,
} from "./api";

describe("queryBook", () => {
  const originalFetch = globalThis.fetch;
  afterEach(() => {
    globalThis.fetch = originalFetch;
  });

  const BOOK_ID = "christmas_carol_e6ddcd76";

  const sampleResponse: QueryResponse = {
    book_id: BOOK_ID,
    question: "Who is Marley?",
    search_type: "GRAPH_COMPLETION",
    current_chapter: 2,
    results: [
      {
        content: "Marley was dead: to begin with.",
        entity_type: "Character",
        chapter: 1,
      },
    ],
    result_count: 1,
  };

  it("POSTs JSON to /books/{id}/query with question, search_type, max_chapter", async () => {
    const mockFetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: () => Promise.resolve(sampleResponse),
    });
    globalThis.fetch = mockFetch as unknown as typeof fetch;

    const result = await queryBook(BOOK_ID, "Who is Marley?", 2);

    expect(mockFetch).toHaveBeenCalledTimes(1);
    const [url, init] = mockFetch.mock.calls[0];
    expect(url).toBe(`http://localhost:8000/books/${BOOK_ID}/query`);
    expect(init.method).toBe("POST");
    expect(init.headers).toMatchObject({ "Content-Type": "application/json" });
    const body = JSON.parse(init.body as string);
    expect(body).toEqual({
      question: "Who is Marley?",
      search_type: "GRAPH_COMPLETION",
      max_chapter: 2,
    });
    expect(result).toEqual(sampleResponse);
  });

  it("throws QueryRateLimitError on 429", async () => {
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 429,
      json: () => Promise.resolve({ detail: "too many" }),
    }) as unknown as typeof fetch;

    await expect(queryBook(BOOK_ID, "q", 1)).rejects.toBeInstanceOf(
      QueryRateLimitError,
    );
    await expect(queryBook(BOOK_ID, "q", 1)).rejects.toBeInstanceOf(QueryError);
  });

  it("throws QueryServerError on 500", async () => {
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 500,
      json: () => Promise.resolve({ detail: "boom" }),
    }) as unknown as typeof fetch;

    await expect(queryBook(BOOK_ID, "q", 1)).rejects.toBeInstanceOf(QueryServerError);
  });

  it("throws QueryServerError on 503", async () => {
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 503,
      json: () => Promise.resolve({}),
    }) as unknown as typeof fetch;

    await expect(queryBook(BOOK_ID, "q", 1)).rejects.toBeInstanceOf(QueryServerError);
  });

  it("throws QueryServerError on 4xx other than 429", async () => {
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 404,
      json: () => Promise.resolve({ detail: "nope" }),
    }) as unknown as typeof fetch;

    await expect(queryBook(BOOK_ID, "q", 1)).rejects.toBeInstanceOf(QueryServerError);
  });

  it("throws QueryNetworkError when fetch itself rejects", async () => {
    globalThis.fetch = vi
      .fn()
      .mockRejectedValue(new TypeError("network down")) as unknown as typeof fetch;

    await expect(queryBook(BOOK_ID, "q", 1)).rejects.toBeInstanceOf(QueryNetworkError);
  });

  it("sets status property on thrown errors for the UI to branch on", async () => {
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 429,
      json: () => Promise.resolve({}),
    }) as unknown as typeof fetch;

    try {
      await queryBook(BOOK_ID, "q", 1);
    } catch (err) {
      expect((err as QueryRateLimitError).status).toBe(429);
    }
  });
});
