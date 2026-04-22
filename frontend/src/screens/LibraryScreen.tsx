import { useEffect, useState } from "react";
import { useLocation } from "react-router-dom";
import { NavBar } from "../components/NavBar";
import { BookCard } from "../components/BookCard";
import { TextInput } from "../components/TextInput";
import { Button } from "../components/Button";
import { Row } from "../components/layout";
import { IcPlus, IcSearch } from "../components/icons";
import { fetchBooks, type Book } from "../lib/api";

type State =
  | { kind: "loading" }
  | { kind: "error"; message: string }
  | { kind: "ok"; books: Book[] };

export function LibraryScreen() {
  const [state, setState] = useState<State>({ kind: "loading" });
  const { pathname } = useLocation();

  useEffect(() => {
    let cancelled = false;
    setState({ kind: "loading" });
    fetchBooks()
      .then((books) => {
        if (!cancelled) setState({ kind: "ok", books });
      })
      .catch((err: unknown) => {
        if (!cancelled)
          setState({
            kind: "error",
            message: err instanceof Error ? err.message : String(err),
          });
      });
    return () => {
      cancelled = true;
    };
  }, [pathname]);

  return (
    <div className="br" style={{ minHeight: "100vh", background: "var(--paper-0)" }}>
      <NavBar />
      <div style={{ maxWidth: 1040, margin: "0 auto", padding: "48px 32px 80px" }}>
        <div
          style={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "flex-end",
            marginBottom: 40,
          }}
        >
          <div>
            <div
              style={{
                fontFamily: "var(--sans)",
                fontSize: 12,
                letterSpacing: 1.6,
                textTransform: "uppercase",
                color: "var(--ink-3)",
                marginBottom: 10,
              }}
            >
              Your shelf
            </div>
            <h1
              style={{
                margin: 0,
                fontFamily: "var(--serif)",
                fontWeight: 400,
                fontSize: 44,
                letterSpacing: -0.8,
                color: "var(--ink-0)",
                lineHeight: 1.1,
              }}
            >
              Your library.
            </h1>
          </div>
          <Row gap={10}>
            <div style={{ width: 240 }}>
              <TextInput
                size="sm"
                icon={<IcSearch size={13} />}
                placeholder="Search your books"
              />
            </div>
            <Button variant="secondary" icon={<IcPlus size={13} />}>
              Add book
            </Button>
          </Row>
        </div>

        {state.kind === "loading" && (
          <div
            role="status"
            style={{ fontFamily: "var(--sans)", fontSize: 14, color: "var(--ink-2)" }}
          >
            Loading your books…
          </div>
        )}

        {state.kind === "error" && (
          <div
            role="alert"
            style={{
              fontFamily: "var(--sans)",
              fontSize: 14,
              color: "var(--err)",
              padding: 16,
              border: "1px solid var(--paper-2)",
              borderRadius: "var(--r-md)",
              background: "var(--paper-00)",
            }}
          >
            Couldn't load your books. ({state.message})
          </div>
        )}

        {state.kind === "ok" && (
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(4, 1fr)",
              gap: 40,
              rowGap: 56,
            }}
          >
            {state.books.map((b) => (
              <BookCard
                key={b.book_id}
                book_id={b.book_id}
                title={b.title}
                total_chapters={b.total_chapters}
                current_chapter={b.current_chapter}
              />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
