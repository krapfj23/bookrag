import { useEffect, useRef, useState } from "react";
import type { AssistantSource } from "../../components/AssistantBubble";
import {
  QueryError,
  QueryRateLimitError,
  type Book,
  type QueryResponse,
} from "../../lib/api";

export type ChatMessage =
  | { id: string; role: "user"; text: string }
  | {
      id: string;
      role: "assistant";
      status: "thinking" | "ok" | "error";
      text: string;
      sources?: AssistantSource[];
    };

const ERR_GENERIC = "Something went wrong. Try again.";
const ERR_RATELIMIT = "Too many requests, slow down.";
const EMPTY_RESULT_TEXT =
  "I don't have anything in your read-so-far that answers that. Try rephrasing, or read further.";

type Deps = {
  bookId: string;
  book: Book | null;
  queryBook: (
    book_id: string,
    question: string,
    max_chapter: number,
  ) => Promise<QueryResponse>;
  // Optional hooks so the screen can coordinate (e.g., clear the spoiler
  // cutoff) without the chat hook knowing about annotations.
  pendingExcerpt?: string | null;
  onPendingCleared?: () => void;
  onAnswered?: () => void;
};

// Owns the chat thread: message list, draft, submit flow, and the
// transcript auto-scroll ref. Errors map to copy synchronously; the
// caller just feeds the hook a `queryBook` and reacts to completions.
export function useChatState({
  bookId,
  book,
  queryBook,
  pendingExcerpt,
  onPendingCleared,
  onAnswered,
}: Deps) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [draft, setDraft] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const transcriptEndRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    const el = transcriptEndRef.current;
    if (el?.scrollIntoView) {
      el.scrollIntoView({ block: "end" });
    }
  }, [messages]);

  async function submit() {
    const trimmed = draft.trim();
    if (!trimmed || !book || submitting) return;

    const userId = crypto.randomUUID();
    const thinkingId = crypto.randomUUID();
    const maxChapter = book.current_chapter;
    // Attach the selection excerpt as a quoted preamble so the backend
    // sees the context the user highlighted. The UI still shows the
    // clean user message in the UserBubble.
    const queryText = pendingExcerpt
      ? `About "${pendingExcerpt}": ${trimmed}`
      : trimmed;

    setMessages((prev) => [
      ...prev,
      { id: userId, role: "user", text: trimmed },
      {
        id: thinkingId,
        role: "assistant",
        status: "thinking",
        text: "Thinking…",
      },
    ]);
    setDraft("");
    onPendingCleared?.();
    setSubmitting(true);

    try {
      const resp = await queryBook(bookId, queryText, maxChapter);
      const hasResults = resp.result_count > 0 && resp.results.length > 0;
      const sources: AssistantSource[] = hasResults
        ? resp.results
            .filter((r): r is typeof r & { chapter: number } => r.chapter != null)
            .map((r) => ({ text: r.content, chapter: r.chapter }))
        : [];
      // Prefer the GraphRAG-synthesized answer. Fall back to chapter-less
      // raw results only if the LLM synthesis was empty.
      const synthesized = resp.answer?.trim() ?? "";
      const proseResults = hasResults
        ? resp.results.filter((r) => r.chapter == null)
        : [];
      const answerText =
        synthesized.length > 0
          ? synthesized
          : hasResults
            ? proseResults.map((r) => r.content).join("\n\n") ||
              sources.map((s) => s.text).join("\n\n")
            : EMPTY_RESULT_TEXT;

      setMessages((prev) =>
        prev.map((m) =>
          m.id === thinkingId
            ? {
                id: thinkingId,
                role: "assistant",
                status: "ok",
                text: answerText,
                sources: sources.length > 0 ? sources : undefined,
              }
            : m,
        ),
      );
    } catch (err) {
      const copy =
        err instanceof QueryRateLimitError
          ? ERR_RATELIMIT
          : err instanceof QueryError
            ? ERR_GENERIC
            : ERR_GENERIC;
      setMessages((prev) =>
        prev.map((m) =>
          m.id === thinkingId
            ? {
                id: thinkingId,
                role: "assistant",
                status: "error",
                text: copy,
              }
            : m,
        ),
      );
    } finally {
      setSubmitting(false);
      onAnswered?.();
    }
  }

  return {
    messages,
    draft,
    setDraft,
    submitting,
    submit,
    transcriptEndRef,
  };
}
