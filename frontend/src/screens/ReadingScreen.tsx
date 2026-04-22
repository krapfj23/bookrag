import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { fetchChapter, type Chapter } from "../lib/api";
import { paginate, type Spread } from "../lib/reader/paginator";
import { BookSpread } from "../components/reader/BookSpread";
import { useReadingCursor } from "../lib/reader/useReadingCursor";
import { NavBar } from "../components/NavBar";

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
          <div style={{ width: "min(1100px, 100%)" }}>
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
            />
          </div>
        )}
      </div>
    </div>
  );
}
