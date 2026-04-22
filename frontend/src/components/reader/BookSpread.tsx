import { Paragraph } from "./Paragraph";
import type { Page } from "../../lib/reader/paginator";
import type { SentenceMark } from "./Sentence";

function PageSide({
  page,
  cursor,
  dropCapFirst,
  folio,
  chapterHeader,
  marksBySid,
  onMarkClick,
}: {
  page: Page;
  cursor: string;
  dropCapFirst: boolean;
  folio: number;
  chapterHeader?: { num: number; title: string; totalChapters: number };
  marksBySid?: Map<string, SentenceMark[]>;
  onMarkClick?: (cardId: string) => void;
}) {
  return (
    <div
      className="rr-page"
      style={{
        background: "var(--paper-00)",
        padding: "52px 44px 40px",
        position: "relative",
        minHeight: 720,
        fontFamily: "var(--serif)",
        fontSize: 15,
        lineHeight: 1.72,
        color: "var(--ink-0)",
      }}
    >
      {chapterHeader && (
        <>
          <div
            style={{
              fontFamily: "var(--serif)",
              fontStyle: "italic",
              fontSize: 11.5,
              letterSpacing: "0.4px",
              color: "var(--ink-3)",
              marginBottom: 10,
            }}
          >
            Chapter {chapterHeader.num} · of {chapterHeader.totalChapters}
          </div>
          <h2
            style={{
              margin: "0 0 26px",
              fontFamily: "var(--serif)",
              fontWeight: 400,
              fontSize: 22,
              letterSpacing: -0.3,
              color: "var(--ink-0)",
            }}
          >
            {chapterHeader.title}
          </h2>
        </>
      )}
      {page.map((p, i) => (
        <Paragraph
          key={`${p.paragraph_idx}-${i}`}
          paragraphIdx={p.paragraph_idx}
          sentences={p.sentences}
          fogStartSid={cursor}
          // Drop cap only applies to the first BODY paragraph of the first
          // spread — never to scene breaks or epigraphs.
          dropCap={
            dropCapFirst &&
            i === 0 &&
            !p.isContinuation &&
            (p.kind ?? "body") === "body"
          }
          kind={p.kind}
          marksBySid={marksBySid}
          onMarkClick={onMarkClick}
        />
      ))}
      <div
        style={{
          position: "absolute",
          bottom: 18,
          left: 44,
          right: 44,
          display: "flex",
          justifyContent: "space-between",
          fontFamily: "var(--serif)",
          fontStyle: "italic",
          fontSize: 11,
          color: "var(--ink-3)",
        }}
      >
        <span style={{ fontFamily: "var(--mono)" }}>{folio}</span>
      </div>
    </div>
  );
}

export function BookSpread({
  chapterNum,
  chapterTitle,
  totalChapters,
  left,
  right,
  folioLeft,
  folioRight,
  cursor,
  isFirstSpread = false,
  marksBySid,
  onMarkClick,
}: {
  chapterNum: number;
  chapterTitle: string;
  totalChapters: number;
  left: Page;
  right: Page;
  folioLeft: number;
  folioRight: number;
  cursor: string;
  isFirstSpread?: boolean;
  marksBySid?: Map<string, SentenceMark[]>;
  onMarkClick?: (cardId: string) => void;
}) {
  return (
    <div
      className="rr-book"
      data-testid="book-spread"
      style={{
        width: 920,
        minHeight: 780,
        display: "grid",
        gridTemplateColumns: "1fr 1fr",
        background: "var(--paper-00)",
        borderRadius: 3,
        boxShadow:
          "0 30px 70px -24px rgba(28,24,18,.2), 0 10px 20px -8px rgba(28,24,18,.08)",
        position: "relative",
        overflow: "hidden",
      }}
    >
      <PageSide
        page={left}
        cursor={cursor}
        dropCapFirst={isFirstSpread}
        folio={folioLeft}
        chapterHeader={{ num: chapterNum, title: chapterTitle, totalChapters }}
        marksBySid={marksBySid}
        onMarkClick={onMarkClick}
      />
      <PageSide
        page={right}
        cursor={cursor}
        dropCapFirst={false}
        folio={folioRight}
        marksBySid={marksBySid}
        onMarkClick={onMarkClick}
      />
      <div
        aria-hidden="true"
        style={{
          position: "absolute",
          left: "calc(50% - 15px)",
          top: 0,
          bottom: 0,
          width: 30,
          background:
            "linear-gradient(to right, transparent 0%, color-mix(in oklab, var(--ink-0) 7%, transparent) 50%, transparent 100%)",
          pointerEvents: "none",
        }}
      />
    </div>
  );
}
