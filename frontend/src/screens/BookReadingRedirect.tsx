import { useEffect, useState } from "react";
import { Navigate, useParams } from "react-router-dom";
import { fetchBooks, type Book } from "../lib/api";

type State =
  | { kind: "loading" }
  | { kind: "error"; message: string }
  | { kind: "redirect"; to: string };

export function BookReadingRedirect() {
  const { bookId } = useParams<{ bookId: string }>();
  const [state, setState] = useState<State>({ kind: "loading" });

  useEffect(() => {
    let cancelled = false;
    if (!bookId) {
      setState({ kind: "error", message: "Missing book id" });
      return;
    }
    fetchBooks()
      .then((books: Book[]) => {
        if (cancelled) return;
        const match = books.find((b) => b.book_id === bookId);
        if (!match) {
          setState({ kind: "error", message: `Book '${bookId}' not found` });
          return;
        }
        setState({
          kind: "redirect",
          to: `/books/${bookId}/read/${match.current_chapter}`,
        });
      })
      .catch((err: unknown) => {
        if (cancelled) return;
        setState({
          kind: "error",
          message: err instanceof Error ? err.message : String(err),
        });
      });
    return () => {
      cancelled = true;
    };
  }, [bookId]);

  if (state.kind === "redirect") {
    return <Navigate replace to={state.to} />;
  }
  if (state.kind === "error") {
    return (
      <div
        role="alert"
        style={{
          padding: 40,
          fontFamily: "var(--sans)",
          color: "var(--err)",
          textAlign: "center",
        }}
      >
        {state.message}
      </div>
    );
  }
  return (
    <div
      role="status"
      style={{
        padding: 40,
        fontFamily: "var(--sans)",
        fontSize: 14,
        color: "var(--ink-2)",
        textAlign: "center",
      }}
    >
      Opening your book…
    </div>
  );
}
