// Seed annotations for the Margin Marks demo. Persistence is a future slice;
// these live in-memory and render inline on matching chapter paragraphs.

export type AnnotationKind = "note" | "query";

export interface Annotation {
  id: string;
  book_id: string;
  chapter: number;
  paragraph_index: number; // 0-indexed within the chapter's paragraphs[]
  match: string; // exact substring inside the paragraph text
  kind: AnnotationKind;
  created_at: string; // display string, e.g. "2h ago"
  tags?: string[];
  // Note: body is the user-written reflection
  body?: string;
  // Query: question + short assistant excerpt
  question?: string;
  answer_excerpt?: string;
  bookmarked?: boolean;
}

// Demo data anchored to real paragraph content in A Christmas Carol.
// Paragraph indexes chosen to land near the top of each chapter so the
// annotations are visible without scrolling during demo walkthroughs.
export const SEED_ANNOTATIONS: Annotation[] = [
  {
    id: "n1",
    book_id: "christmas_carol_e6ddcd76",
    chapter: 1,
    paragraph_index: 57, // raw file: "Mind! I don't mean to say…"
    match: "a door-nail",
    kind: "note",
    created_at: "2h ago",
    tags: ["#idiom", "#opening"],
    body: 'Dickens opens with the dead-metaphor pun — "dead as a door-nail" — and then immediately interrogates the phrase. Sets the tone: the book will question what "dead" even means.',
  },
  {
    id: "q1",
    book_id: "christmas_carol_e6ddcd76",
    chapter: 1,
    paragraph_index: 57,
    match: "coffin-nail",
    kind: "query",
    created_at: "2h ago",
    question: "Why does Dickens linger on the door-nail vs coffin-nail distinction?",
    answer_excerpt:
      'Dickens is foregrounding language itself — the narrator self-corrects and questions idiom, which sets up a whole book about what words like "dead," "merry," and "wealth" really mean.',
  },
  {
    id: "n2",
    book_id: "christmas_carol_e6ddcd76",
    chapter: 2,
    paragraph_index: 0,
    match: "The Last of the Spirits",
    kind: "note",
    created_at: "just now",
    tags: ["#structure"],
    body: 'Chapter title as incantation. The definite article ("The Last") does a lot of work — it tells you before you read a word that this is the terminal spirit, the one who closes the frame.',
  },
  {
    id: "q2",
    book_id: "christmas_carol_e6ddcd76",
    chapter: 2,
    paragraph_index: 1,
    match: "that man who lay upon the bed",
    kind: "query",
    created_at: "just now",
    question: 'Who is the "man" Scrooge is asking about?',
    answer_excerpt:
      "Scrooge is looking at his own corpse — the Spirit has shown him a future in which he has died unloved. The question is rhetorical dread, not confusion.",
    bookmarked: true,
  },
];

export function annotationsForChapter(bookId: string, chapter: number): Annotation[] {
  return SEED_ANNOTATIONS.filter((a) => a.book_id === bookId && a.chapter === chapter);
}
