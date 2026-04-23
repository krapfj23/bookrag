import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useNavigate, useParams, useLocation } from "react-router-dom";
import { fetchChapter, fetchBook, queryBook, setProgress, type Chapter } from "../lib/api";
import { paginate, type PaginatorBox, type Spread } from "../lib/reader/paginator";
import { BookSpread } from "../components/reader/BookSpread";
import { useReadingCursor } from "../lib/reader/useReadingCursor";
import { ReaderTopBar } from "../components/reader/ReaderTopBar";
import { SelectionToolbar, type SelectionAction } from "../components/SelectionToolbar";
import { MarginColumn } from "../components/reader/MarginColumn";
import { useCards } from "../lib/reader/useCards";
import { useSelectionToolbar } from "../lib/reader/useSelectionToolbar";
import { askAndStream, followupAndStream } from "../lib/reader/askFlow";
import { compareSid } from "../lib/reader/sidCompare";
import type { SentenceMark } from "../components/reader/Sentence";
import { useReadingMode } from "../lib/reader/useReadingMode";
import { PacingLabel } from "../components/reader/PacingLabel";
import { PageTurnArrow } from "../components/reader/PageTurnArrow";
import { ProgressHairline } from "../components/reader/ProgressHairline";
import { ReadingModeLegend } from "../components/reader/ReadingModeLegend";
import { NotePeekPopover } from "../components/reader/NotePeekPopover";

type Body =
  | { kind: "loading" }
  | { kind: "error"; message: string }
  | { kind: "ok"; chapter: Chapter; spreads: Spread[] };

type PeekState = { body: string; x: number; y: number; createdAt: string } | null;

export function ReadingScreen() {
  const { bookId = "", chapterNum = "1" } = useParams<{
    bookId: string;
    chapterNum: string;
  }>();
  const n = Number.parseInt(chapterNum, 10) || 1;
  const navigate = useNavigate();
  const location = useLocation();

  const [body, setBody] = useState<Body>({ kind: "loading" });
  const [spreadIdx, setSpreadIdx] = useState(0);
  const [bookAuthor, setBookAuthor] = useState("");
  const stageRef = useRef<HTMLDivElement | null>(null);
  const bookRef = useRef<HTMLDivElement | null>(null);
  // bookRootEl is a state mirror of bookRef so MarginColumn rerenders when ref is set.
  const [bookRootEl, setBookRootEl] = useState<HTMLDivElement | null>(null);

  const { mode, toggle } = useReadingMode(bookId);
  const [peek, setPeek] = useState<PeekState>(null);

  // Page box responds to window size + reading-mode font bump.
  // Two pages side-by-side, a gutter, plus the 400px margin column + gap.
  const [viewport, setViewport] = useState<{ w: number; h: number }>(() =>
    typeof window === "undefined"
      ? { w: 1280, h: 900 }
      : { w: window.innerWidth, h: window.innerHeight },
  );
  useEffect(() => {
    function onResize() {
      setViewport({ w: window.innerWidth, h: window.innerHeight });
    }
    window.addEventListener("resize", onResize);
    return () => window.removeEventListener("resize", onResize);
  }, []);

  const box: PaginatorBox = useMemo(() => {
    // Reading-mode ON hides the sidebar, so the book can center with equal
    // ambient margins. Conservative mode reserves a 400px margin-card column.
    const marginColumnWidth = mode === "on" ? 0 : 400;
    const gap = mode === "on" ? 0 : 28;
    const stagePadding = 48;
    const availableForSpread = Math.max(
      640,
      viewport.w - marginColumnWidth - gap - stagePadding,
    );
    // Clamp page width so spreads don't get absurdly wide on 4K screens.
    // Reading-mode pages are slightly wider than conservative.
    const maxPage = mode === "on" ? 620 : 560;
    const pageWidth = Math.max(360, Math.min(maxPage, Math.floor(availableForSpread / 2) - 8));
    // Height tracks viewport too; leave room for topbar + stage padding.
    const pageHeight = Math.max(560, Math.min(960, viewport.h - 140));
    const fontPx = mode === "on" ? 18 : 15;
    const paddingPx = mode === "on" ? 56 : 48;
    return { pageWidth, pageHeight, paddingPx, fontPx, lineHeight: 1.72 };
  }, [viewport.w, viewport.h, mode]);

  // Reset spreadIdx to 0 whenever the chapter number changes. Without this,
  // arriving at chapter N+1 inherits the previous chapter's last spreadIdx,
  // which prevents ArrowLeft from navigating back to the previous chapter
  // (it just decrements inside the new chapter instead). Backward nav sets
  // location.state.landOnLastSpread, which is handled in the repaginate
  // effect after spreads are computed.
  useEffect(() => {
    setSpreadIdx(0);
  }, [bookId, n]);

  // Load chapter (fetch only — pagination is a separate memo so resize /
  // reading-mode toggles don't refetch).
  const [rawChapter, setRawChapter] = useState<Chapter | null>(null);
  useEffect(() => {
    let cancelled = false;
    setBody({ kind: "loading" });
    setRawChapter(null);
    fetchChapter(bookId, n)
      .then((chapter) => {
        if (cancelled) return;
        setRawChapter(chapter);
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
  }, [bookId, n]);

  // Repaginate whenever chapter text OR box dimensions change.
  useEffect(() => {
    if (!rawChapter) return;
    const spreads = paginate(rawChapter.paragraphs_anchored ?? [], box);
    const landOnLast = (location.state as { landOnLastSpread?: boolean } | null)?.landOnLastSpread ?? false;
    setSpreadIdx((prev) => {
      if (landOnLast) return Math.max(0, spreads.length - 1);
      // Preserve position across repaginate where possible, but clamp so the
      // counter can never exceed total spreads (fixes "pages multiply" when
      // rapidly switching modes / resizing).
      return Math.min(prev, Math.max(0, spreads.length - 1));
    });
    setBody({ kind: "ok", chapter: rawChapter, spreads });
  }, [rawChapter, box, location.state]);

  // Sync backend reading progress whenever the chapter changes. This is the
  // source of truth the /query fog-of-war filter uses when no max_chapter is
  // provided, and it caps max_chapter when one is. Without it, queries are
  // over-filtered against a stale current_chapter.
  useEffect(() => {
    let cancelled = false;
    setProgress(bookId, n).catch(() => {
      if (cancelled) return;
      // Silent: reading still works from the client cursor; only the query
      // fog-of-war is affected.
    });
    return () => { cancelled = true; };
  }, [bookId, n]);

  // Fetch book metadata once for the author field in the folio row.
  useEffect(() => {
    let cancelled = false;
    fetchBook(bookId).then((book) => {
      if (!cancelled && book?.author) setBookAuthor(book.author);
    });
    return () => { cancelled = true; };
  }, [bookId]);

  const firstSid =
    body.kind === "ok" ? body.spreads[0]?.firstSid ?? "p1.s1" : "p1.s1";
  const { cursor, advanceTo } = useReadingCursor(bookId, n, firstSid);

  const current: Spread | null =
    body.kind === "ok" ? body.spreads[spreadIdx] ?? null : null;

  const turnForward = useCallback(() => {
    if (body.kind !== "ok") return;
    if (spreadIdx < body.spreads.length - 1) {
      const next = spreadIdx + 1;
      setSpreadIdx(next);
      const nextSpread = body.spreads[next];
      if (nextSpread) advanceTo(nextSpread.lastSid);
    } else if (body.chapter.num < body.chapter.total_chapters) {
      // At the last spread of this chapter — advance to next chapter.
      navigate(`/books/${bookId}/read/${body.chapter.num + 1}`);
    }
    // else: last spread of last chapter — no-op.
  }, [body, spreadIdx, advanceTo, navigate, bookId]);

  const turnBackward = useCallback(() => {
    if (body.kind !== "ok") return;
    if (spreadIdx > 0) {
      setSpreadIdx(spreadIdx - 1);
      // Cursor does NOT rewind (AC 10).
    } else if (body.chapter.num > 1) {
      // At spread 0 of a non-first chapter — go back to previous chapter's last spread.
      navigate(`/books/${bookId}/read/${body.chapter.num - 1}`, {
        state: { landOnLastSpread: true },
      });
    }
    // else: spread 0 of chapter 1 — no-op.
  }, [body, spreadIdx, navigate, bookId]);

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.key === "ArrowRight") {
        e.preventDefault();
        turnForward();
      } else if (e.key === "ArrowLeft") {
        e.preventDefault();
        turnBackward();
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [turnForward, turnBackward]);

  // Whenever the visible spread changes (mount, chapter jump, page turn),
  // advance the reading cursor to the last sid of the new spread. advanceTo
  // is forward-only, so this won't rewind when navigating backward.
  useEffect(() => {
    if (current?.lastSid) advanceTo(current.lastSid);
  }, [current, advanceTo]);

  const title = body.kind === "ok" ? body.chapter.title : "";
  const total = body.kind === "ok" ? body.chapter.total_chapters : 0;

  // Cards state
  const {
    cards,
    createAsk,
    createHighlight,
    createNote,
    updateAsk,
    updateNote,
    removeCard,
    findByAnchorAndKind,
    appendFollowup,
    setAskLoading,
    setAskStreaming,
  } = useCards(bookId);

  const { selection, clear: clearSelection } = useSelectionToolbar(bookRef);

  const [focusedCardId, setFocusedCardId] = useState<string | null>(null);
  const [newlyCreatedNoteId, setNewlyCreatedNoteId] = useState<string | null>(null);
  const [focusedComposerCardId, setFocusedComposerCardId] = useState<string | null>(null);
  const flashTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const flash = useCallback((id: string) => {
    setFocusedCardId(id);
    if (flashTimer.current) clearTimeout(flashTimer.current);
    flashTimer.current = setTimeout(() => setFocusedCardId(null), 620);
  }, []);

  // visibleSids = ONLY the current spread's sids. Cards from previous spreads
  // are not shown when the reader turns forward (no cross-spread accumulation).
  const visibleSids: Set<string> = useMemo(() => {
    if (!current) return new Set();
    const s = new Set<string>();
    for (const page of [current.left, current.right]) {
      for (const para of page) {
        for (const sent of para.sentences) s.add(sent.sid);
      }
    }
    return s;
  }, [current]);

  // Compute left/right sids and folios from the current spread.
  const leftSids: Set<string> = useMemo(() => {
    if (!current) return new Set();
    const s = new Set<string>();
    for (const para of current.left) {
      for (const sent of para.sentences) s.add(sent.sid);
    }
    return s;
  }, [current]);

  const rightSids: Set<string> = useMemo(() => {
    if (!current) return new Set();
    const s = new Set<string>();
    for (const para of current.right) {
      for (const sent of para.sentences) s.add(sent.sid);
    }
    return s;
  }, [current]);

  const leftFolio = spreadIdx * 2 + 1;
  const rightFolio = spreadIdx * 2 + 2;

  // currentSpreadSids = visibleSids (same set — kept for MarginColumn cross-page prefix).
  const currentSpreadSids = visibleSids;

  const marksBySid: Map<string, SentenceMark[]> = useMemo(() => {
    const m = new Map<string, SentenceMark[]>();
    for (const c of cards) {
      if (!visibleSids.has(c.anchor)) continue;
      const arr = m.get(c.anchor) ?? [];
      arr.push({ kind: c.kind, cardId: c.id });
      m.set(c.anchor, arr);
    }
    return m;
  }, [cards, visibleSids]);

  const onMarkClick = useCallback(
    (cardId: string) => {
      const el = document.querySelector(`[data-card-id="${cardId}"]`);
      if (el) el.scrollIntoView({ behavior: "smooth", block: "center" });
      flash(cardId);
    },
    [flash],
  );

  const onAction = useCallback(
    async (action: SelectionAction) => {
      if (!selection) return;
      const { anchorSid, quote } = selection;
      const chapter = n;
      if (action === "highlight") {
        const existing = findByAnchorAndKind(anchorSid, "highlight");
        if (existing) {
          removeCard(existing.id);
        } else {
          const id = createHighlight({ anchor: anchorSid, quote, chapter });
          flash(id);
        }
        clearSelection();
        return;
      }
      if (action === "note") {
        const existing = findByAnchorAndKind(anchorSid, "note");
        if (existing) {
          flash(existing.id);
          clearSelection();
          return;
        }
        const id = createNote({ anchor: anchorSid, quote, chapter });
        setNewlyCreatedNoteId(id);
        flash(id);
        clearSelection();
        return;
      }
      // ask — S5: duplicate focuses card AND follow-up composer
      const existing = findByAnchorAndKind(anchorSid, "ask");
      if (existing) {
        flash(existing.id);
        setFocusedComposerCardId(existing.id);
        clearSelection();
        return;
      }
      clearSelection();
      const id = await askAndStream({
        anchor: anchorSid,
        quote,
        chapter,
        maxChapter: chapter,
        bookId,
        createAsk,
        updateAsk,
        findExisting: (a) => {
          const e = findByAnchorAndKind(a, "ask");
          return e ? { id: e.id } : undefined;
        },
        queryBook: (b, q, mc) => queryBook(b, q, mc),
        setAskLoading,
        setAskStreaming,
        streamMinMs: 40,
        streamMaxMs: 80,
      });
      flash(id);
    },
    [selection, n, bookId, clearSelection, findByAnchorAndKind, flash, createHighlight, createNote, createAsk, removeCard, updateAsk, setAskLoading, setAskStreaming],
  );

  const onBodyChange = useCallback(
    (id: string, next: string) => updateNote(id, next),
    [updateNote],
  );

  const onBodyCommit = useCallback(
    (id: string) => {
      const card = cards.find((c) => c.id === id);
      if (card && card.kind === "note" && card.body.trim() === "") {
        removeCard(id);
      }
      setNewlyCreatedNoteId((prev) => (prev === id ? null : prev));
    },
    [cards, removeCard],
  );

  const onJump = useCallback(
    (sid: string) => {
      const root = bookRef.current;
      if (!root) return;
      const el = root.querySelector(`[data-sid="${sid}"]`);
      if (!el) return;
      el.scrollIntoView({ behavior: "smooth", block: "center" });
      el.classList.add("rr-card-flash");
      setTimeout(() => el.classList.remove("rr-card-flash"), 620);
    },
    [],
  );

  const onFollowup = useCallback(
    (cardId: string, question: string) => {
      followupAndStream({
        cardId,
        bookId,
        maxChapter: n,
        question,
        appendFollowup,
        updateAsk,
        queryBook: (b, q, mc) => queryBook(b, q, mc),
        streamMinMs: 40,
        streamMaxMs: 80,
      });
    },
    [bookId, n, appendFollowup, updateAsk],
  );

  // Fog check for Ask button disabled state
  const askDisabled =
    !!selection && compareSid(selection.anchorSid, cursor) > 0;

  // Progress computation for the hairline.
  const progress = useMemo(() => {
    if (body.kind !== "ok" || !current) return 0;
    const totalParagraphs = body.chapter.paragraphs_anchored?.length ?? 0;
    if (totalParagraphs === 0) return 0;
    // Find the last paragraph on the right page; fall back to left if right empty.
    const rightPage = current.right;
    const leftPage = current.left;
    const lastRightPara = rightPage[rightPage.length - 1];
    const lastLeftPara = leftPage[leftPage.length - 1];
    const lastPara = lastRightPara ?? lastLeftPara;
    if (!lastPara) return 0;
    // paragraph_idx is 1-based; compute progress as fraction of paragraphs read.
    return Math.min(Math.max(lastPara.paragraph_idx / totalParagraphs, 0), 1);
  }, [body, current]);

  // Hover delegation for note-peek (only when reading mode is on).
  const peekTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    if (mode !== "on") {
      // Clear any pending peek and hide the popover when turning off.
      if (peekTimerRef.current) clearTimeout(peekTimerRef.current);
      setPeek(null);
      return;
    }

    const root = bookRef.current;
    if (!root) return;

    function onMouseOver(e: MouseEvent) {
      const target = e.target as HTMLElement | null;
      if (!target) return;
      const noteSpan = target.closest<HTMLElement>('[data-kind="note"]');
      if (!noteSpan) return;
      if (peekTimerRef.current) clearTimeout(peekTimerRef.current);
      peekTimerRef.current = setTimeout(() => {
        const sid = noteSpan.getAttribute("data-sid");
        if (!sid) return;
        // Find the note card for this sid.
        const noteCard = cards.find((c) => c.kind === "note" && c.anchor === sid);
        if (!noteCard || noteCard.kind !== "note") return;
        const rect = noteSpan.getBoundingClientRect();
        setPeek({
          body: noteCard.body,
          x: rect.left + rect.width / 2,
          y: rect.top,
          createdAt: noteCard.createdAt ?? "",
        });
      }, 150);
    }

    function onMouseOut(e: MouseEvent) {
      const target = e.target as HTMLElement | null;
      if (!target) return;
      const noteSpan = target.closest<HTMLElement>('[data-kind="note"]');
      if (!noteSpan) return;
      if (peekTimerRef.current) clearTimeout(peekTimerRef.current);
      setPeek(null);
    }

    root.addEventListener("mouseover", onMouseOver);
    root.addEventListener("mouseout", onMouseOut);
    return () => {
      root.removeEventListener("mouseover", onMouseOver);
      root.removeEventListener("mouseout", onMouseOut);
      if (peekTimerRef.current) clearTimeout(peekTimerRef.current);
    };
  }, [mode, cards, bookRootEl]); // bookRootEl included to re-run when ref is set

  const isAtFirstSpread = spreadIdx === 0 && (body.kind !== "ok" || body.chapter.num === 1);
  const isAtLastSpread =
    body.kind === "ok" &&
    spreadIdx === body.spreads.length - 1 &&
    body.chapter.num === body.chapter.total_chapters;

  const rootBackground =
    mode === "on"
      ? "radial-gradient(ellipse 80% 60% at center 40%, oklch(96% 0.012 85), oklch(93% 0.015 80) 80%)"
      : "var(--paper-0)";

  return (
    <div
      className="br"
      style={{
        minHeight: "100vh",
        background: rootBackground,
        transition: "background 420ms cubic-bezier(.2,.7,.2,1)",
      }}
      data-testid="reading-screen"
      data-reading-mode={mode}
    >
      <ReaderTopBar
        title={title}
        mode={mode}
        onToggleMode={toggle}
        spreadIdx={spreadIdx}
        totalSpreads={body.kind === "ok" ? body.spreads.length : undefined}
      />

      <div
        ref={stageRef}
        style={{
          padding: "24px",
          display: "grid",
          placeItems: "center",
          minHeight: "calc(100vh - 52px)",
        }}
      >
        {body.kind === "loading" && (
          <div role="status" style={{ color: "var(--ink-2)" }}>
            Loading chapter…
          </div>
        )}
        {body.kind === "error" && (
          <div role="alert" style={{ color: "var(--err)" }}>
            Couldn't load the chapter. ({body.message})
          </div>
        )}
        {body.kind === "ok" && current && (
          <div
            style={{
              display: "grid",
              // Reading-mode ON: single centered column (no sidebar reservation).
              // Conservative: two columns — book + 400px margin card column.
              gridTemplateColumns:
                mode === "on" ? `${box.pageWidth * 2}px` : `${box.pageWidth * 2}px 400px`,
              gap: mode === "on" ? 0 : 28,
              alignItems: "start",
              justifyContent: "center",
              width: "auto",
              maxWidth: "100%",
            }}
          >
            <div ref={(el) => { bookRef.current = el; setBookRootEl(el); }}>
              <BookSpread
                chapterNum={body.chapter.num}
                chapterTitle={body.chapter.title}
                totalChapters={total}
                left={current.left}
                right={current.right}
                folioLeft={spreadIdx * 2 + 1}
                folioRight={spreadIdx * 2 + 2}
                cursor={cursor}
                isFirstSpread={spreadIdx === 0}
                marksBySid={marksBySid}
                onMarkClick={onMarkClick}
                author={bookAuthor}
                pageWidth={box.pageWidth}
                pageHeight={box.pageHeight}
                paddingPx={box.paddingPx}
                fontPx={box.fontPx}
                lineHeight={box.lineHeight}
              />
            </div>
            {mode !== "on" && (
              <MarginColumn
                cards={cards}
                visibleSids={visibleSids}
                focusedCardId={focusedCardId}
                newlyCreatedNoteId={newlyCreatedNoteId}
                onBodyChange={onBodyChange}
                onBodyCommit={onBodyCommit}
                leftSids={leftSids}
                rightSids={rightSids}
                leftFolio={leftFolio}
                rightFolio={rightFolio}
                currentSpreadSids={currentSpreadSids}
                bookRoot={bookRootEl}
                onJump={onJump}
                onFollowup={onFollowup}
                focusedComposerCardId={focusedComposerCardId}
                hidden={false}
              />
            )}
          </div>
        )}
        {selection && (
          <SelectionToolbar
            top={selection.rect.top + window.scrollY}
            left={selection.rect.left + selection.rect.width / 2 + window.scrollX}
            onAction={onAction}
            disabled={{ ask: askDisabled }}
          />
        )}
      </div>

      {/* Reading mode chrome — conditionally rendered when mode is on */}
      {mode === "on" && body.kind === "ok" && (
        <>
          <div
            style={{
              position: "fixed",
              top: 16,
              left: "50%",
              transform: "translateX(-50%)",
              zIndex: 99,
            }}
          >
            <PacingLabel num={body.chapter.num} total={body.chapter.total_chapters} />
          </div>
          <PageTurnArrow
            direction="left"
            onClick={turnBackward}
            disabled={isAtFirstSpread}
          />
          <PageTurnArrow
            direction="right"
            onClick={turnForward}
            disabled={isAtLastSpread}
          />
          <ProgressHairline progress={progress} />
          <ReadingModeLegend />
        </>
      )}

      <NotePeekPopover
        visible={!!peek}
        body={peek?.body ?? ""}
        x={peek?.x ?? 0}
        y={peek?.y ?? 0}
        createdAt={peek?.createdAt ?? ""}
      />
    </div>
  );
}
