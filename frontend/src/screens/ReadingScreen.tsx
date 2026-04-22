import { useEffect, useMemo, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { NavBar } from "../components/NavBar";
import { ChapterRow, type ChapterRowState } from "../components/ChapterRow";
import { ProgressPill } from "../components/ProgressPill";
import { ProgressiveBlur } from "../components/ProgressiveBlur";
import { LockState } from "../components/LockState";
import { Button } from "../components/Button";
import { Row } from "../components/layout";
import { IcArrowL, IcArrowR } from "../components/icons";
import { UserBubble } from "../components/UserBubble";
import { AssistantBubble, type AssistantSource } from "../components/AssistantBubble";
import { ChatInput } from "../components/ChatInput";
import { AnnotatedParagraph } from "../components/AnnotatedParagraph";
import { AnnotationPeek } from "../components/AnnotationPeek";
import { AnnotationRail } from "../components/AnnotationRail";
import {
  AnnotationPanel,
  type PanelTab,
} from "../components/AnnotationPanel";
import {
  annotationsForChapter,
  SEED_ANNOTATIONS,
  type Annotation,
} from "../lib/annotations";
import {
  fetchBooks,
  fetchChapter,
  fetchChapters,
  setProgress,
  queryBook,
  QueryRateLimitError,
  QueryError,
  type Book,
  type Chapter,
  type ChapterSummary,
} from "../lib/api";

type BodyState =
  | { kind: "idle" }
  | { kind: "loading" }
  | { kind: "error"; message: string }
  | { kind: "ok"; chapter: Chapter };

type ChatMessage =
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

  // ── Chat (Thread tab) state ──────────────────────────────────────────
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

  async function handleChatSubmit() {
    const trimmed = draft.trim();
    if (!trimmed || !book || submitting) return;

    const userId = crypto.randomUUID();
    const thinkingId = crypto.randomUUID();
    const maxChapter = book.current_chapter;

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
    setSubmitting(true);

    try {
      const resp = await queryBook(bookId, trimmed, maxChapter);
      const hasResults = resp.result_count > 0 && resp.results.length > 0;
      const sources: AssistantSource[] = hasResults
        ? resp.results
            .filter((r): r is typeof r & { chapter: number } =>
              r.chapter != null
            )
            .map((r) => ({ text: r.content, chapter: r.chapter }))
        : [];
      const proseResults = hasResults
        ? resp.results.filter((r) => r.chapter == null)
        : [];
      const answerText = hasResults
        ? proseResults.map((r) => r.content).join("\n\n")
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
            : m
        )
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
            : m
        )
      );
    } finally {
      setSubmitting(false);
    }
  }

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

  // ── Annotations state ───────────────────────────────────────────────
  // All seed annotations for this book, plus annotations for the chapter
  // currently in view (used by AnnotatedParagraph to decorate prose).
  const bookAnnotations = useMemo(
    () => SEED_ANNOTATIONS.filter((a) => a.book_id === bookId),
    [bookId],
  );
  const chapterAnnotations = useMemo(
    () => annotationsForChapter(bookId, n),
    [bookId, n],
  );
  const notes = bookAnnotations.filter((a) => a.kind === "note");
  const highlights = bookAnnotations.filter((a) => a.kind === "query");

  // Click state: which inline annotation has the peek open.
  const [peek, setPeek] = useState<{ annotation: Annotation } | null>(null);
  // Panel state: collapsed (rail) vs expanded; current tab; focused item.
  const [panelOpen, setPanelOpen] = useState(false);
  const [panelTab, setPanelTab] = useState<PanelTab>("thread");
  const [focusedAnnotationId, setFocusedAnnotationId] = useState<
    string | undefined
  >(undefined);

  function openPeek(a: Annotation) {
    // Clicking the same annotation a second time closes the peek.
    setPeek((prev) => (prev?.annotation.id === a.id ? null : { annotation: a }));
  }

  function openInPanel(a: Annotation) {
    setPanelOpen(true);
    setPanelTab(a.kind === "note" ? "notes" : "highlights");
    setFocusedAnnotationId(a.id);
    setPeek(null);
  }

  const spoilerSafeLabel = `safe through ch. ${book?.current_chapter ?? 1}`;

  const threadContent = (
    <>
      <div
        style={{
          flex: 1,
          padding: "20px 20px 16px",
          display: "flex",
          flexDirection: "column",
          gap: 20,
          overflow: "auto",
        }}
      >
        {messages.length === 0 && (
          <div
            role="status"
            style={{
              flex: 1,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              textAlign: "center",
              fontFamily: "var(--serif)",
              fontStyle: "italic",
              fontSize: 15,
              color: "var(--ink-3)",
              padding: "40px 24px",
            }}
          >
            Ask about what you've read.
          </div>
        )}
        {messages.map((m) =>
          m.role === "user" ? (
            <UserBubble key={m.id} text={m.text} />
          ) : (
            <AssistantBubble
              key={m.id}
              text={m.text}
              sources={m.status === "ok" ? m.sources : undefined}
              thinking={m.status === "thinking"}
            />
          )
        )}
        <div ref={transcriptEndRef} />
      </div>
      <div style={{ padding: "14px 16px 18px" }}>
        <ChatInput
          value={draft}
          onChange={setDraft}
          onSubmit={handleChatSubmit}
          disabled={submitting}
        />
      </div>
    </>
  );

  return (
    <div
      className="br"
      style={{ minHeight: "100vh", background: "var(--paper-0)" }}
    >
      <NavBar />
      <div
        style={{
          display: "grid",
          gridTemplateColumns: panelOpen
            ? "260px 1fr 400px"
            : "260px 1fr 48px",
          minHeight: "calc(100vh - 56px)",
          transition: "grid-template-columns var(--dur-slow) var(--ease-out)",
        }}
      >
        {/* LEFT — chapter nav */}
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

        {/* CENTER — reading */}
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
                      position: "relative",
                    }}
                  >
                    {body.chapter.paragraphs.map((p, i) => {
                      const paragraphAnnots = chapterAnnotations.filter(
                        (a) => a.paragraph_index === i,
                      );
                      const peekForThisParagraph =
                        peek !== null &&
                        peek.annotation.paragraph_index === i
                          ? peek.annotation
                          : null;
                      return (
                        <div
                          key={i}
                          style={{ position: "relative", margin: "0 0 22px" }}
                        >
                          <p style={{ margin: 0 }}>
                            <AnnotatedParagraph
                              text={p}
                              annotations={paragraphAnnots}
                              activeId={peek?.annotation.id}
                              onAnnotationClick={openPeek}
                            />
                          </p>
                          {peekForThisParagraph && (
                            <AnnotationPeek
                              annotation={peekForThisParagraph}
                              top={36}
                              left={0}
                              onOpenInPanel={() =>
                                openInPanel(peekForThisParagraph)
                              }
                            />
                          )}
                        </div>
                      );
                    })}
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

        {/* RIGHT — 48px rail OR 400px expanded panel */}
        {panelOpen ? (
          <AnnotationPanel
            tab={panelTab}
            onTabChange={setPanelTab}
            onClose={() => {
              setPanelOpen(false);
              setFocusedAnnotationId(undefined);
            }}
            thread={threadContent}
            notes={notes}
            highlights={highlights}
            spoilerSafeLabel={spoilerSafeLabel}
            focusedAnnotationId={focusedAnnotationId}
            threadCount={messages.length}
          />
        ) : (
          <AnnotationRail
            onOpen={(t) => {
              setPanelOpen(true);
              setPanelTab(t);
            }}
            pips={{
              thread: messages.length > 0,
              notes: notes.length > 0,
            }}
          />
        )}
      </div>
    </div>
  );
}
