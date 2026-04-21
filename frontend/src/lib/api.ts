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

const BASE_URL = "http://localhost:8000";

export async function fetchBooks(): Promise<Book[]> {
  const resp = await fetch(`${BASE_URL}/books`);
  if (!resp.ok) {
    throw new Error(`GET /books failed: ${resp.status}`);
  }
  return (await resp.json()) as Book[];
}

export async function uploadBook(file: File): Promise<UploadResponse> {
  const form = new FormData();
  form.append("file", file, file.name);

  const resp = await fetch(`${BASE_URL}/books/upload`, {
    method: "POST",
    body: form,
  });

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
  const resp = await fetch(`${BASE_URL}/books/${book_id}/status`);
  if (!resp.ok) {
    throw new Error(`GET /books/${book_id}/status failed: ${resp.status}`);
  }
  return (await resp.json()) as PipelineState;
}
