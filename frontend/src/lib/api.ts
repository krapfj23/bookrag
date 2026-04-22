export type Book = {
  book_id: string;
  title: string;
  total_chapters: number;
  current_chapter: number;
  ready_for_query: boolean;
};

export type StageName =
  | "parse_epub"
  | "run_booknlp"
  | "resolve_coref"
  | "discover_ontology"
  | "review_ontology"
  | "run_cognee_batches"
  | "validate";

export type StageStatus = "pending" | "running" | "complete" | "failed";

export type PipelineStage = {
  status: StageStatus;
  duration_seconds?: number;
  error?: string;
};

export type PipelineOverall = "pending" | "processing" | "complete" | "failed";

export type PipelineState = {
  book_id: string;
  status: PipelineOverall;
  stages: Record<StageName, PipelineStage>;
  current_batch: number | null;
  total_batches: number | null;
  ready_for_query: boolean;
};

export type UploadResponse = {
  book_id: string;
  message: string;
};

export class UploadError extends Error {
  readonly status: number;
  constructor(status: number, message: string) {
    super(message);
    this.name = "UploadError";
    this.status = status;
  }
}

const BASE_URL =
  (import.meta.env.VITE_API_BASE_URL as string | undefined) ?? "http://localhost:8000";

// Thrown when a request exceeds `timeoutMs` and the AbortController fires.
export class NetworkError extends Error {
  constructor(message = "Request timed out") {
    super(message);
    this.name = "NetworkError";
  }
}

// Wrap fetch() with an AbortController so every request has a finite lifetime.
// Default 30s; uploads pass 120s. Aborts surface as NetworkError so callers
// can distinguish "request died" from "server said no".
export async function fetchWithTimeout(
  url: string,
  init: RequestInit = {},
  timeoutMs = 30_000,
): Promise<Response> {
  const controller = new AbortController();
  const id = setTimeout(() => controller.abort(), timeoutMs);
  try {
    return await fetch(url, { ...init, signal: controller.signal });
  } catch (err) {
    if (err instanceof Error && err.name === "AbortError") {
      throw new NetworkError(`Request to ${url} timed out after ${timeoutMs}ms`);
    }
    throw err;
  } finally {
    clearTimeout(id);
  }
}

export async function fetchBooks(): Promise<Book[]> {
  const resp = await fetchWithTimeout(`${BASE_URL}/books`);
  if (!resp.ok) {
    throw new Error(`GET /books failed: ${resp.status}`);
  }
  return (await resp.json()) as Book[];
}

export async function uploadBook(file: File): Promise<UploadResponse> {
  const form = new FormData();
  form.append("file", file, file.name);

  const resp = await fetchWithTimeout(
    `${BASE_URL}/books/upload`,
    {
      method: "POST",
      body: form,
    },
    120_000,
  );

  if (resp.ok) {
    return (await resp.json()) as UploadResponse;
  }

  let detail = "";
  try {
    const body = (await resp.json()) as { detail?: string };
    detail = body.detail ?? "";
  } catch {
    detail = "";
  }

  const message = mapUploadError(resp.status, detail);
  throw new UploadError(resp.status, message);
}

function mapUploadError(status: number, detail: string): string {
  if (status === 400) return "Only .epub files are accepted";
  if (status === 413) return "File too large (max 500 MB)";
  if (status === 429) return "Too many pipelines running, try again later";
  if (detail) return detail;
  return `Upload failed (${status})`;
}

export async function fetchStatus(book_id: string): Promise<PipelineState> {
  const resp = await fetchWithTimeout(`${BASE_URL}/books/${book_id}/status`);
  if (!resp.ok) {
    throw new Error(`GET /books/${book_id}/status failed: ${resp.status}`);
  }
  return (await resp.json()) as PipelineState;
}

export type ChapterSummary = {
  num: number;
  title: string;
  word_count: number;
};

export type AnchoredSentence = { sid: string; text: string };
export type ParagraphKind = "body" | "scene_break" | "epigraph";
export type AnchoredParagraph = {
  paragraph_idx: number;
  sentences: AnchoredSentence[];
  // Optional: missing on responses from pre-Phase-A backends; the renderer
  // treats undefined as "body".
  kind?: ParagraphKind;
};

export type Chapter = {
  num: number;
  title: string;
  paragraphs: string[];
  paragraphs_anchored: AnchoredParagraph[];
  anchors_fallback: boolean;
  has_prev: boolean;
  has_next: boolean;
  total_chapters: number;
};

export type ProgressResponse = {
  book_id: string;
  current_chapter: number;
};

export async function fetchChapters(book_id: string): Promise<ChapterSummary[]> {
  const resp = await fetchWithTimeout(`${BASE_URL}/books/${book_id}/chapters`);
  if (!resp.ok) {
    throw new Error(`GET /books/${book_id}/chapters failed: ${resp.status}`);
  }
  return (await resp.json()) as ChapterSummary[];
}

export async function fetchChapter(book_id: string, n: number): Promise<Chapter> {
  const resp = await fetchWithTimeout(`${BASE_URL}/books/${book_id}/chapters/${n}`);
  if (!resp.ok) {
    throw new Error(`GET /books/${book_id}/chapters/${n} failed: ${resp.status}`);
  }
  return (await resp.json()) as Chapter;
}

export async function setProgress(
  book_id: string,
  current_chapter: number,
): Promise<ProgressResponse> {
  const resp = await fetchWithTimeout(`${BASE_URL}/books/${book_id}/progress`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ current_chapter }),
  });
  if (!resp.ok) {
    throw new Error(`POST /books/${book_id}/progress failed: ${resp.status}`);
  }
  return (await resp.json()) as ProgressResponse;
}

// ---------------------------------------------------------------------------
// Query endpoint (slice 4)
// ---------------------------------------------------------------------------

export type QuerySearchType =
  | "GRAPH_COMPLETION"
  | "CHUNKS"
  | "SUMMARIES"
  | "RAG_COMPLETION";

export type QueryResult = {
  content: string;
  entity_type: string | null;
  chapter: number | null;
};

export type QueryResponse = {
  book_id: string;
  question: string;
  search_type: string;
  current_chapter: number;
  // LLM-synthesized answer from the graph context. Empty string when
  // the synthesis call failed server-side and the backend is serving
  // only raw sources.
  answer: string;
  results: QueryResult[];
  result_count: number;
};

export class QueryError extends Error {
  readonly status: number;
  constructor(status: number, message: string) {
    super(message);
    this.name = "QueryError";
    this.status = status;
  }
}

export class QueryRateLimitError extends QueryError {
  constructor(message = "Too many requests, slow down.") {
    super(429, message);
    this.name = "QueryRateLimitError";
  }
}

export class QueryServerError extends QueryError {
  constructor(status: number, message = "Something went wrong. Try again.") {
    super(status, message);
    this.name = "QueryServerError";
  }
}

export class QueryNetworkError extends QueryError {
  constructor(message = "Something went wrong. Try again.") {
    super(0, message);
    this.name = "QueryNetworkError";
  }
}

export async function queryBook(
  book_id: string,
  question: string,
  max_chapter: number,
  search_type: QuerySearchType = "GRAPH_COMPLETION",
): Promise<QueryResponse> {
  let resp: Response;
  try {
    resp = await fetchWithTimeout(`${BASE_URL}/books/${book_id}/query`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question, search_type, max_chapter }),
    });
  } catch (err) {
    // Preserve the existing error-class discriminator: both raw fetch failures
    // and NetworkError timeouts surface as QueryNetworkError for UI branching.
    if (err instanceof NetworkError) {
      throw new QueryNetworkError();
    }
    throw new QueryNetworkError();
  }

  if (resp.ok) {
    return (await resp.json()) as QueryResponse;
  }

  if (resp.status === 429) {
    throw new QueryRateLimitError();
  }
  throw new QueryServerError(resp.status);
}
