export type Book = {
  book_id: string;
  title: string;
  total_chapters: number;
  current_chapter: number;
  ready_for_query: boolean;
};

const BASE_URL = "http://localhost:8000";

export async function fetchBooks(): Promise<Book[]> {
  const resp = await fetch(`${BASE_URL}/books`);
  if (!resp.ok) {
    throw new Error(`GET /books failed: ${resp.status}`);
  }
  return (await resp.json()) as Book[];
}
