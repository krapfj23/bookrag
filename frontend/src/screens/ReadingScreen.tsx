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
import { AnnotatedParagraph, fogLevelFor } from "../components/AnnotatedParagraph";
import { AnnotationPeek } from "../components/AnnotationPeek";
import { AnnotationRail } from "../components/AnnotationRail";
import { AnnotationPanel, type PanelTab } from "../components/AnnotationPanel";
import { SelectionToolbar, type SelectionAction } from "../components/SelectionToolbar";
import { NoteComposer } from "../components/NoteComposer";
import { IcClose } from "../components/icons";
import { SEED_ANNOTATIONS, type Annotation } from "../lib/annotations";
import {
  appendUserAnnotation,
  clearCutoff,
  getCutoff,
  loadUserAnnotations,
  setCutoff,
  type Cutoff,
} from "../lib/storage";
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
      .catch((err: unknown) => {
        // One-shot load, not a poll loop — log and leave the sidebar empty.
        // Center column's own fetch+error path handles user-facing surface.
        console.error("reading sidebar load failed", err);
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
    // `book` identity is unused in the body after the current_chapter read;
    // including it would re-fire the chapter fetch on unrelated reloads.
    // eslint-disable-next-line react-hooks/exhaustive-deps
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
    // Attach the selection excerpt as a quoted preamble so the backend
    // sees the context the user highlighted. The UI still shows the
    // clean user message in the UserBubble.
    const attachedExcerpt = pendingQuery?.excerpt ?? null;
    const queryText = attachedExcerpt
      ? `About "${attachedExcerpt}": ${trimmed}`
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
    setPendingQuery(null);
    setSubmitting(true);

    try {
      const resp = await queryBook(bookId, queryText, maxChapter);
      const hasResults = resp.result_count > 0 && resp.results.length > 0;
      const sources: AssistantSource[] = hasResults
        ? resp.results
            .filter((r): r is typeof r & { chapter: number } => r.chapter != null)
            .map((r) => ({ text: r.content, chapter: r.chapter }))
        : [];
      // Prefer the GraphRAG-synthesized answer from the backend. Fall back
      // to chapter-less raw results only if the LLM synthesis was empty
      // (e.g., Cognee unavailable). Final fallback: the empty-result copy.
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
      // Query resolved — fog was only a "I'm asking about this" marker, not
      // a persistent reading-position cutoff. Clear it so the reader can
      // continue unimpeded.
      clearCurrentCutoff();
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
      // Error path: clear the fog too — the user got a response (even if bad)
      // and shouldn't be stuck staring at blurred text.
      clearCurrentCutoff();
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
  // Seed annotations + user-created (localStorage) annotations, merged.
  const [userAnnotations, setUserAnnotations] = useState<Annotation[]>(() =>
    loadUserAnnotations(),
  );
  const bookAnnotations = useMemo(
    () => [...SEED_ANNOTATIONS, ...userAnnotations].filter((a) => a.book_id === bookId),
    [bookId, userAnnotations],
  );
  const chapterAnnotations = useMemo(
    () => bookAnnotations.filter((a) => a.chapter === n),
    [bookAnnotations, n],
  );
  const notes = bookAnnotations.filter((a) => a.kind === "note");
  const highlights = bookAnnotations.filter((a) => a.kind === "query");

  // Click state: which inline annotation has the peek open.
  const [peek, setPeek] = useState<{ annotation: Annotation } | null>(null);
  // Panel state: collapsed (rail) vs expanded; current tab; focused item.
  const [panelOpen, setPanelOpen] = useState(false);
  const [panelTab, setPanelTab] = useState<PanelTab>("thread");
  const [focusedAnnotationId, setFocusedAnnotationId] = useState<string | undefined>(
    undefined,
  );

  // ── Selection + fog state ──────────────────────────────────────────
  // Current text selection (if any) inside the reading column.
  const [selection, setSelection] = useState<{
    excerpt: string;
    paragraphIndex: number;
    charOffsetStart: number;
    charOffsetEnd: number;
    toolbarTop: number;
    toolbarLeft: number;
  } | null>(null);
  // Pending note composer (opens a modal when user clicks "Note" in the toolbar)
  const [noteDraft, setNoteDraft] = useState<{
    excerpt: string;
    paragraph_index: number;
  } | null>(null);
  // Selection context chip to show above the chat input after "Ask"
  const [pendingQuery, setPendingQuery] = useState<{ excerpt: string } | null>(null);
  // Per-chapter cutoff, loaded from localStorage on chapter change.
  const [cutoff, setCutoffState] = useState<Cutoff | null>(null);
  const readerRef = useRef<HTMLDivElement | null>(null);

  // Load the cutoff for the current (book, chapter) when they change.
  useEffect(() => {
    setCutoffState(getCutoff(bookId, n));
  }, [bookId, n]);

  // Detect text selection inside the reading column.
  useEffect(() => {
    function onMouseUp() {
      const sel = window.getSelection();
      if (!sel || sel.isCollapsed || sel.rangeCount === 0) {
        setSelection(null);
        return;
      }
      const range = sel.getRangeAt(0);
      const root = readerRef.current;
      if (!root || !root.contains(range.commonAncestorContainer)) {
        setSelection(null);
        return;
      }
      // Find the enclosing paragraph <p data-paragraph-index="…">
      let node: Node | null = range.commonAncestorContainer;
      while (node && node !== root) {
        if (node instanceof HTMLElement && node.dataset.paragraphIndex !== undefined) {
          break;
        }
        node = node.parentNode;
      }
      if (!(node instanceof HTMLElement) || node === root) {
        setSelection(null);
        return;
      }
      const paragraphIndex = Number.parseInt(node.dataset.paragraphIndex ?? "0", 10);
      const excerpt = sel.toString().trim();
      if (excerpt.length === 0) {
        setSelection(null);
        return;
      }
      // Derive char offsets against the paragraph's text content.
      const paragraphText = node.textContent ?? "";
      const charOffsetStart = paragraphText.indexOf(excerpt);
      const charOffsetEnd =
        charOffsetStart >= 0 ? charOffsetStart + excerpt.length : paragraphText.length;
      const rect = range.getBoundingClientRect();
      setSelection({
        excerpt,
        paragraphIndex,
        charOffsetStart: Math.max(0, charOffsetStart),
        charOffsetEnd,
        toolbarTop: rect.top,
        toolbarLeft: rect.left + rect.width / 2,
      });
    }
    document.addEventListener("mouseup", onMouseUp);
    return () => document.removeEventListener("mouseup", onMouseUp);
  }, []);

  function openPeek(a: Annotation) {
    setPeek((prev) => (prev?.annotation.id === a.id ? null : { annotation: a }));
  }

  function openInPanel(a: Annotation) {
    setPanelOpen(true);
    setPanelTab(a.kind === "note" ? "notes" : "highlights");
    setFocusedAnnotationId(a.id);
    setPeek(null);
  }

  function onSelectionAction(action: SelectionAction) {
    if (!selection) return;
    const s = selection;
    const timestamp = "just now";
    if (action === "ask") {
      // 1. Create a query annotation on the selection (persists)
      const a: Annotation = {
        id: `q_${Date.now()}`,
        book_id: bookId,
        chapter: n,
        paragraph_index: s.paragraphIndex,
        match: s.excerpt,
        kind: "query",
        created_at: timestamp,
        question: "",
        answer_excerpt: "",
      };
      setUserAnnotations(appendUserAnnotation(a));
      // 2. Set the cutoff to start fog immediately after the selection
      const c: Cutoff = {
        book_id: bookId,
        chapter: n,
        paragraph_index: s.paragraphIndex,
        char_offset_end: s.charOffsetEnd,
        excerpt: s.excerpt,
      };
      setCutoff(c);
      setCutoffState(c);
      // 3. Open Thread tab with the selection context chip primed
      setPendingQuery({ excerpt: s.excerpt });
      setPanelOpen(true);
      setPanelTab("thread");
    } else if (action === "note") {
      setNoteDraft({
        excerpt: s.excerpt,
        paragraph_index: s.paragraphIndex,
      });
    } else if (action === "highlight") {
      const a: Annotation = {
        id: `h_${Date.now()}`,
        book_id: bookId,
        chapter: n,
        paragraph_index: s.paragraphIndex,
        match: s.excerpt,
        kind: "note", // a highlight renders as a soft-highlight span
        created_at: timestamp,
        body: "",
      };
      setUserAnnotations(appendUserAnnotation(a));
    }
    // Always collapse the selection + toolbar after an action
    window.getSelection()?.removeAllRanges();
    setSelection(null);
  }

  function saveNote(body: string, tags: string[]) {
    if (!noteDraft) return;
    const a: Annotation = {
      id: `n_${Date.now()}`,
      book_id: bookId,
      chapter: n,
      paragraph_index: noteDraft.paragraph_index,
      match: noteDraft.excerpt,
      kind: "note",
      created_at: "just now",
      body,
      tags: tags.length > 0 ? tags : undefined,
    };
    setUserAnnotations(appendUserAnnotation(a));
    setNoteDraft(null);
  }

  function clearCurrentCutoff() {
    clearCutoff(bookId, n);
    setCutoffState(null);
  }

  // Pressing Escape anywhere on the page clears the fog — a fast out for
  // readers who set a cutoff, then want back to unobstructed reading.
  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape" && cutoff) {
        clearCurrentCutoff();
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [cutoff, bookId, n]);

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
          ),
        )}
        <div ref={transcriptEndRef} />
      </div>
      <div style={{ padding: "14px 16px 18px" }}>
        {pendingQuery && (
          <div className="selection-context-chip" data-testid="selection-context-chip">
            <div style={{ flex: 1 }}>
              <div className="ctx-label">asking about</div>
              <div className="ctx-excerpt">"{pendingQuery.excerpt}"</div>
            </div>
            <button
              type="button"
              aria-label="Remove selection context"
              onClick={() => setPendingQuery(null)}
            >
              <IcClose size={11} />
            </button>
          </div>
        )}
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
    <div className="br" style={{ minHeight: "100vh", background: "var(--paper-0)" }}>
      <NavBar />
      <div
        style={{
          display: "grid",
          gridTemplateColumns: panelOpen ? "260px 1fr 400px" : "260px 1fr 48px",
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
                  chapterList?.find((c) => c.num === n)?.title ?? `Chapter ${n}`
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
                      <p style={{ margin: "0 0 22px" }}>{body.chapter.paragraphs[0]}</p>
                    </div>
                  </ProgressiveBlur>
                ) : (
                  <div
                    ref={readerRef}
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
                        peek !== null && peek.annotation.paragraph_index === i
                          ? peek.annotation
                          : null;
                      // Fog calc: paragraphs strictly AFTER the cutoff paragraph
                      // are foggy; the cutoff paragraph itself is split in
                      // AnnotatedParagraph via cutoffCharOffset.
                      const isCutoffPara =
                        cutoff !== null && cutoff.paragraph_index === i;
                      const fogDistance =
                        cutoff !== null ? i - cutoff.paragraph_index : 0;
                      const fogLevel = fogLevelFor(
                        isCutoffPara ? 0 : Math.max(0, fogDistance),
                      );
                      return (
                        <div
                          key={i}
                          style={{ position: "relative", margin: "0 0 22px" }}
                        >
                          <p data-paragraph-index={i} style={{ margin: 0 }}>
                            <AnnotatedParagraph
                              text={p}
                              annotations={paragraphAnnots}
                              activeId={peek?.annotation.id}
                              onAnnotationClick={openPeek}
                              fogLevel={fogLevel}
                              cutoffCharOffset={
                                isCutoffPara ? cutoff!.char_offset_end : undefined
                              }
                            />
                          </p>
                          {peekForThisParagraph && (
                            <AnnotationPeek
                              annotation={peekForThisParagraph}
                              top={36}
                              left={0}
                              onOpenInPanel={() => openInPanel(peekForThisParagraph)}
                            />
                          )}
                        </div>
                      );
                    })}
                    {cutoff && (
                      <div
                        style={{
                          display: "flex",
                          justifyContent: "center",
                          marginTop: 40,
                        }}
                      >
                        <div className="reading-up-to">
                          <span style={{ opacity: 0.7 }}>Reading up to:</span>
                          <span className="excerpt">"{cutoff.excerpt}"</span>
                          <button
                            type="button"
                            aria-label="Clear reading cutoff"
                            onClick={clearCurrentCutoff}
                          >
                            <IcClose size={11} />
                          </button>
                        </div>
                      </div>
                    )}
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
              // Leaving the panel = done with the current question.
              // Drop any lingering fog so the reader gets their book back.
              setPendingQuery(null);
              clearCurrentCutoff();
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

      {selection && (
        <SelectionToolbar
          top={selection.toolbarTop}
          left={selection.toolbarLeft}
          onAction={onSelectionAction}
        />
      )}
      {noteDraft && (
        <NoteComposer
          excerpt={noteDraft.excerpt}
          onCancel={() => setNoteDraft(null)}
          onSave={saveNote}
        />
      )}
    </div>
  );
}
