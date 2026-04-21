import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import {
  fetchBooks,
  uploadBook,
  fetchStatus,
  UploadError,
  type PipelineState,
} from "./api";

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
        "Too many pipelines running, try again later"
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
      "http://localhost:8000/books/a_christmas_carol_a1b2c3d4/status"
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
