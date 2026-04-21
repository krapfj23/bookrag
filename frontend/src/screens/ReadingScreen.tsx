import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { NavBar } from "../components/NavBar";
import { ChapterRow, type ChapterRowState } from "../components/ChapterRow";
import { ProgressPill } from "../components/ProgressPill";
import { ProgressiveBlur } from "../components/ProgressiveBlur";
import { LockState } from "../components/LockState";
import { Button } from "../components/Button";
import { Row } from "../components/layout";
import { IcArrowL, IcArrowR, IcChat } from "../components/icons";
import {
  fetchBooks,
  fetchChapter,
  fetchChapters,
  setProgress,
  type Book,
  type Chapter,
  type ChapterSummary,
} from "../lib/api";

type BodyState =
  | { kind: "idle" }
  | { kind: "loading" }
  | { kind: "error"; message: string }
  | { kind: "ok"; chapter: Chapter };

export function ReadingScreen() {
  const { bookId = "", chapterNum = "1" } = useParams<{
    bookId: string;
    chapterNum: string;
  }>();
  const n = Number.parseInt(chapterNum, 10) || 1;
  const navigate = useNavigate();

  const [book, setBook] = useState<Book | null>(null);
  const [chapterList, setChapterList] = useState<ChapterSummary[] | null>(null);
  const [body, setBody] = useState<BodyState>({ kind: "idle" });

  // Fetch the book record + chapter list once
  useEffect(() => {
    let cancelled = false;
    Promise.all([fetchBooks(), fetchChapters(bookId)])
      .then(([books, chapters]) => {
        if (cancelled) return;
        setBook(books.find((b) => b.book_id === bookId) ?? null);
        setChapterList(chapters);
      })
      .catch(() => {
        // sidebar stays empty; center column error-states will show separately
      });
    return () => {
      cancelled = true;
    };
  }, [bookId]);

  // Fetch the chapter body every time n changes — unless the chapter is
  // >= current_chapter + 2 (fully locked, no fetch per PRD AC 9).
  useEffect(() => {
    if (!book) return;
    if (n > book.current_chapter + 1) {
      setBody({ kind: "idle" });
      return;
    }
    let cancelled = false;
    setBody({ kind: "loading" });
    fetchChapter(bookId, n)
      .then((chapter) => {
        if (cancelled) return;
        setBody({ kind: "ok", chapter });
      })
      .catch((err: unknown) => {
        if (cancelled) return;
        setBody({
          kind: "error",
          message: err instanceof Error ? err.message : String(err),
        });
      });
    return () => {
      cancelled = true;
    };
  }, [bookId, n, book?.current_chapter]);

  function rowStateFor(num: number): ChapterRowState {
    if (!book) return "locked";
    if (num < book.current_chapter) return "read";
    if (num === book.current_chapter) return "current";
    return "locked";
  }

  async function handleMarkAsRead() {
    if (!book) return;
    const next = n + 1;
    await setProgress(bookId, next);
    // Optimistically refetch the book record so the sidebar reflects new progress
    const fresh = await fetchBooks();
    setBook(fresh.find((b) => b.book_id === bookId) ?? null);
    navigate(`/books/${bookId}/read/${next}`);
  }

  const canPrev = n > 1;
  const canNext =
    body.kind === "ok" &&
    body.chapter.has_next &&
    book !== null &&
    n < book.current_chapter;
  const showMarkAsRead =
    book !== null && n === book.current_chapter && n < book.total_chapters;

  const lockedStrictly = book !== null && n > book.current_chapter + 1;
  const isTeaser = book !== null && n === book.current_chapter + 1;

  return (
    <div
      className="br"
      style={{ minHeight: "100vh", background: "var(--paper-0)" }}
    >
      <NavBar />
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "260px 1fr 440px",
          minHeight: "calc(100vh - 56px)",
        }}
      >
        {/* LEFT */}
        <aside
          style={{
            borderRight: "var(--hairline)",
            padding: "32px 0",
            fontFamily: "var(--sans)",
          }}
        >
          <div style={{ padding: "0 24px 20px" }}>
            <div
              style={{
                fontFamily: "var(--serif)",
                fontStyle: "italic",
                fontSize: 20,
                letterSpacing: -0.3,
                color: "var(--ink-0)",
              }}
            >
              {book?.title ?? "…"}
            </div>
            <div style={{ marginTop: 14 }}>
              <ProgressPill
                current={book?.current_chapter ?? 1}
                total={book?.total_chapters ?? 1}
                variant="soft"
              />
            </div>
          </div>
          <div>
            {(chapterList ?? []).map((c) => (
              <ChapterRow
                key={c.num}
                num={c.num}
                title={c.title}
                state={rowStateFor(c.num)}
                onClick={() => navigate(`/books/${bookId}/read/${c.num}`)}
              />
            ))}
          </div>
        </aside>

        {/* CENTER */}
        <main
          style={{
            padding: "56px 56px 80px",
            position: "relative",
            overflow: "hidden",
          }}
        >
          <div
            style={{
              maxWidth: 620,
              margin: "0 auto",
              position: "relative",
            }}
          >
            {lockedStrictly && body.kind === "idle" && (
              <LockState
                variant="chapterLock"
                chapterNum={n}
                chapterTitle={
                  chapterList?.find((c) => c.num === n)?.title ??
                  `Chapter ${n}`
                }
              />
            )}

            {body.kind === "loading" && (
              <div
                role="status"
                style={{
                  fontFamily: "var(--sans)",
                  fontSize: 14,
                  color: "var(--ink-2)",
                }}
              >
                Loading chapter…
              </div>
            )}
            {body.kind === "error" && (
              <div role="alert" style={{ color: "var(--err)" }}>
                Couldn't load the chapter. ({body.message})
              </div>
            )}
            {body.kind === "ok" && (
              <article>
                <div
                  style={{
                    fontFamily: "var(--sans)",
                    fontSize: 11,
                    letterSpacing: 1.6,
                    textTransform: "uppercase",
                    color: "var(--ink-3)",
                    marginBottom: 12,
                  }}
                >
                  Chapter {body.chapter.num} of {body.chapter.total_chapters}
                </div>
                <h2
                  style={{
                    margin: "0 0 28px",
                    fontFamily: "var(--serif)",
                    fontWeight: 400,
                    fontSize: 30,
                    letterSpacing: -0.5,
                    color: "var(--ink-0)",
                    lineHeight: 1.15,
                  }}
                >
                  {body.chapter.title}
                </h2>
                {isTeaser ? (
                  <ProgressiveBlur locked height={280}>
                    <div
                      style={{
                        fontFamily: "var(--serif)",
                        fontSize: 17,
                        lineHeight: 1.7,
                        color: "var(--ink-0)",
                      }}
                    >
                      <p style={{ margin: "0 0 22px" }}>
                        {body.chapter.paragraphs[0]}
                      </p>
                    </div>
                  </ProgressiveBlur>
                ) : (
                  <div
                    style={{
                      fontFamily: "var(--serif)",
                      fontSize: 17,
                      lineHeight: 1.7,
                      color: "var(--ink-0)",
                    }}
                  >
                    {body.chapter.paragraphs.map((p, i) => (
                      <p
                        key={i}
                        style={{ margin: "0 0 22px" }}
                      >
                        {p}
                      </p>
                    ))}
                  </div>
                )}

                <Row
                  gap={12}
                  style={{
                    marginTop: 48,
                    paddingTop: 24,
                    borderTop: "var(--hairline)",
                    justifyContent: "space-between",
                  }}
                >
                  <button
                    type="button"
                    disabled={!canPrev}
                    onClick={() => navigate(`/books/${bookId}/read/${n - 1}`)}
                    aria-label="Previous chapter"
                    style={{
                      display: "inline-flex",
                      alignItems: "center",
                      gap: 8,
                      padding: "7px 14px",
                      height: 34,
                      fontSize: 14,
                      fontFamily: "var(--sans)",
                      fontWeight: 500,
                      borderRadius: "var(--r-md)",
                      background: "transparent",
                      color: "var(--ink-1)",
                      border: 0,
                      cursor: canPrev ? "pointer" : "not-allowed",
                      opacity: canPrev ? 1 : 0.4,
                    }}
                  >
                    <IcArrowL size={14} /> Previous
                  </button>
                  {showMarkAsRead && (
                    <Button variant="primary" onClick={handleMarkAsRead}>
                      Mark as read
                    </Button>
                  )}
                  <button
                    type="button"
                    disabled={!canNext}
                    onClick={() => navigate(`/books/${bookId}/read/${n + 1}`)}
                    aria-label="Next chapter"
                    style={{
                      display: "inline-flex",
                      alignItems: "center",
                      gap: 8,
                      padding: "7px 14px",
                      height: 34,
                      fontSize: 14,
                      fontFamily: "var(--sans)",
                      fontWeight: 500,
                      borderRadius: "var(--r-md)",
                      background: "transparent",
                      color: "var(--ink-1)",
                      border: 0,
                      cursor: canNext ? "pointer" : "not-allowed",
                      opacity: canNext ? 1 : 0.4,
                    }}
                  >
                    Next <IcArrowR size={14} />
                  </button>
                </Row>
              </article>
            )}
          </div>
        </main>

        {/* RIGHT */}
        <aside
          style={{
            borderLeft: "var(--hairline)",
            display: "flex",
            flexDirection: "column",
            background:
              "color-mix(in oklab, var(--paper-0) 92%, var(--paper-1))",
          }}
        >
          <div
            style={{
              padding: "20px 24px",
              borderBottom: "var(--hairline)",
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
            }}
          >
            <Row gap={8}>
              <IcChat size={14} style={{ color: "var(--ink-2)" }} />
              <span
                style={{
                  fontFamily: "var(--sans)",
                  fontSize: 13,
                  fontWeight: 500,
                  color: "var(--ink-0)",
                  letterSpacing: 0.2,
                }}
              >
                Margin notes
              </span>
            </Row>
            <LockState
              variant="spoilerSafe"
              label={`safe through ch. ${book?.current_chapter ?? 1}`}
            />
          </div>
          <div
            style={{
              flex: 1,
              padding: "24px",
              display: "flex",
              flexDirection: "column",
              alignItems: "center",
              justifyContent: "center",
              gap: 16,
              color: "var(--ink-3)",
              fontFamily: "var(--sans)",
              fontSize: 13,
            }}
          >
            Chat coming soon — available in the next release.
          </div>
          <div style={{ padding: "16px 20px 20px" }}>
            <textarea
              disabled
              aria-disabled="true"
              title="Available in the next release"
              placeholder="Available in the next release"
              rows={1}
              style={{
                width: "100%",
                resize: "none",
                padding: "10px 12px",
                borderRadius: "var(--r-md)",
                border: "1px solid var(--paper-2)",
                background: "var(--paper-1)",
                fontFamily: "var(--serif)",
                fontSize: 14,
                color: "var(--ink-3)",
                cursor: "not-allowed",
                boxSizing: "border-box",
              }}
            />
          </div>
        </aside>
      </div>
    </div>
  );
}
