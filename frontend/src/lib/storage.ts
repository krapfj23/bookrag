// Tiny localStorage helpers with typed keys. Keeps reads/writes in one
// place so the schema version can bump without search-and-replace.

import type { Annotation } from "./annotations";

const ANNOT_KEY = "bookrag:annotations:v1";
const CUTOFF_KEY = "bookrag:cutoffs:v1";

export interface Cutoff {
  book_id: string;
  chapter: number;
  paragraph_index: number;
  // Character offset into the paragraph where the selection ENDS.
  // Everything after this offset in the same paragraph, and every
  // paragraph below, gets progressive fog.
  char_offset_end: number;
  excerpt: string; // the selected text, for the "Reading up to" pill
}

function safeParse<T>(raw: string | null, fallback: T): T {
  if (!raw) return fallback;
  try {
    return JSON.parse(raw) as T;
  } catch {
    return fallback;
  }
}

// ── User annotations ─────────────────────────────────────────────────
export function loadUserAnnotations(): Annotation[] {
  if (typeof localStorage === "undefined") return [];
  return safeParse<Annotation[]>(localStorage.getItem(ANNOT_KEY), []);
}

export function saveUserAnnotations(list: Annotation[]): void {
  if (typeof localStorage === "undefined") return;
  localStorage.setItem(ANNOT_KEY, JSON.stringify(list));
}

export function appendUserAnnotation(a: Annotation): Annotation[] {
  const current = loadUserAnnotations();
  const next = [...current, a];
  saveUserAnnotations(next);
  return next;
}

// ── Cutoffs (per book, per chapter) ─────────────────────────────────
function cutoffMapKey(bookId: string, chapter: number): string {
  return `${bookId}::${chapter}`;
}

export function loadCutoffs(): Record<string, Cutoff> {
  if (typeof localStorage === "undefined") return {};
  return safeParse<Record<string, Cutoff>>(localStorage.getItem(CUTOFF_KEY), {});
}

export function getCutoff(bookId: string, chapter: number): Cutoff | null {
  const all = loadCutoffs();
  return all[cutoffMapKey(bookId, chapter)] ?? null;
}

export function setCutoff(cutoff: Cutoff): void {
  if (typeof localStorage === "undefined") return;
  const all = loadCutoffs();
  all[cutoffMapKey(cutoff.book_id, cutoff.chapter)] = cutoff;
  localStorage.setItem(CUTOFF_KEY, JSON.stringify(all));
}

export function clearCutoff(bookId: string, chapter: number): void {
  if (typeof localStorage === "undefined") return;
  const all = loadCutoffs();
  delete all[cutoffMapKey(bookId, chapter)];
  localStorage.setItem(CUTOFF_KEY, JSON.stringify(all));
}
