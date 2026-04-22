import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { fetchChapter, queryBook, type Chapter } from "../lib/api";
import { paginate, type Spread } from "../lib/reader/paginator";
import { BookSpread } from "../components/reader/BookSpread";
import { useReadingCursor } from "../lib/reader/useReadingCursor";
import { NavBar } from "../components/NavBar";
import { SelectionToolbar, type SelectionAction } from "../components/SelectionToolbar";
import { MarginColumn } from "../components/reader/MarginColumn";
import { useCards } from "../lib/reader/useCards";
import { useSelectionToolbar } from "../lib/reader/useSelectionToolbar";
import { askAndStream } from "../lib/reader/askFlow";
import { compareSid } from "../lib/reader/sidCompare";
import type { SentenceMark } from "../components/reader/Sentence";

type Body =
  | { kind: "loading" }
  | { kind: "error"; message: string }
  | { kind: "ok"; chapter: Chapter; spreads: Spread[] };

export function ReadingScreen() {
  const { bookId = "", chapterNum = "1" } = useParams<{
    bookId: string;
    chapterNum: string;
  }>();
  const n = Number.parseInt(chapterNum, 10) || 1;
  const navigate = useNavigate();

  const [body, setBody] = useState<Body>({ kind: "loading" });
  const [spreadIdx, setSpreadIdx] = useState(0);
  const stageRef = useRef<HTMLDivElement | null>(null);
  const bookRef = useRef<HTMLDivElement | null>(null);

  // Load chapter and paginate.
  useEffect(() => {
    let cancelled = false;
    setBody({ kind: "loading" });
    fetchChapter(bookId, n)
      .then((chapter) => {
        if (cancelled) return;
        const box = {
          pageWidth: 440,
          pageHeight: 720,
          paddingPx: 48,
          fontPx: 15,
          lineHeight: 1.72,
        };
        const spreads = paginate(chapter.paragraphs_anchored ?? [], box);
        setSpreadIdx(0);
        setBody({ kind: "ok", chapter, spreads });
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

  const firstSid =
    body.kind === "ok" ? body.spreads[0]?.firstSid ?? "p1.s1" : "p1.s1";
  const { cursor, advanceTo } = useReadingCursor(bookId, n, firstSid);

  const current: Spread | null =
    body.kind === "ok" ? body.spreads[spreadIdx] ?? null : null;

  const turnForward = useCallback(() => {
    if (body.kind !== "ok") return;
    if (spreadIdx >= body.spreads.length - 1) return;
    const next = spreadIdx + 1;
    setSpreadIdx(next);
    const nextSpread = body.spreads[next];
    if (nextSpread) advanceTo(nextSpread.lastSid);
  }, [body, spreadIdx, advanceTo]);

  const turnBackward = useCallback(() => {
    if (body.kind !== "ok") return;
    if (spreadIdx <= 0) return;
    setSpreadIdx(spreadIdx - 1);
    // Cursor does NOT rewind (AC 10).
  }, [body, spreadIdx]);

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

  const title = body.kind === "ok" ? body.chapter.title : "";
  const total = body.kind === "ok" ? body.chapter.total_chapters : 0;

  // Cards state
  const {
    cards,
    createAsk,
    createNote,
    updateAsk,
    updateNote,
    removeCard,
    findByAnchorAndKind,
  } = useCards(bookId);

  const { selection, clear: clearSelection } = useSelectionToolbar(bookRef);

  const [focusedCardId, setFocusedCardId] = useState<string | null>(null);
  const [newlyCreatedNoteId, setNewlyCreatedNoteId] = useState<string | null>(null);
  const flashTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const flash = useCallback((id: string) => {
    setFocusedCardId(id);
    if (flashTimer.current) clearTimeout(flashTimer.current);
    flashTimer.current = setTimeout(() => setFocusedCardId(null), 620);
  }, []);

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
      // ask
      const existing = findByAnchorAndKind(anchorSid, "ask");
      if (existing) {
        flash(existing.id);
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
      });
      flash(id);
    },
    [selection, n, bookId, clearSelection, findByAnchorAndKind, flash, createNote, createAsk, updateAsk],
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

  // Fog check for Ask button disabled state
  const askDisabled =
    !!selection && compareSid(selection.anchorSid, cursor) > 0;

  return (
    <div
      className="br"
      style={{ minHeight: "100vh", background: "var(--paper-0)" }}
      data-testid="reading-screen"
    >
      <NavBar />
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "1fr auto 1fr",
          alignItems: "center",
          padding: "14px 28px",
          height: 52,
          borderBottom: "var(--hairline)",
        }}
      >
        <button
          type="button"
          onClick={() => navigate("/")}
          style={{
            fontFamily: "var(--sans)",
            fontSize: 13,
            color: "var(--ink-1)",
            justifySelf: "start",
            background: "transparent",
            border: 0,
            cursor: "pointer",
          }}
          aria-label="Back to library"
        >
          ← Library
        </button>
        <div
          style={{
            fontFamily: "var(--serif)",
            fontStyle: "italic",
            fontSize: 14,
            color: "var(--ink-0)",
          }}
        >
          {title}
        </div>
        <div
          aria-hidden="true"
          style={{ justifySelf: "end", color: "var(--ink-3)", fontSize: 12 }}
        >
          {body.kind === "ok"
            ? `${spreadIdx + 1} / ${body.spreads.length}`
            : ""}
        </div>
      </div>

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
              gridTemplateColumns: "1fr 400px",
              gap: 28,
              alignItems: "start",
              width: "min(1240px, 100%)",
            }}
          >
            <div ref={bookRef}>
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
              />
            </div>
            <MarginColumn
              cards={cards}
              visibleSids={visibleSids}
              focusedCardId={focusedCardId}
              newlyCreatedNoteId={newlyCreatedNoteId}
              onBodyChange={onBodyChange}
              onBodyCommit={onBodyCommit}
            />
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
    </div>
  );
}
