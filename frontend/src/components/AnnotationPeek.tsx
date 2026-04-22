import type { Annotation } from "../lib/annotations";
import { IcBookmark, IcEdit, IcExpand, IcPrivate } from "./icons";

interface Props {
  annotation: Annotation;
  top: number;
  left: number;
  onOpenInPanel: () => void;
  onClose?: () => void;
}

export function AnnotationPeek({ annotation, top, left, onOpenInPanel }: Props) {
  return annotation.kind === "note" ? (
    <NotePeekBody a={annotation} top={top} left={left} onOpenInPanel={onOpenInPanel} />
  ) : (
    <QueryPeekBody a={annotation} top={top} left={left} onOpenInPanel={onOpenInPanel} />
  );
}

function NotePeekBody({
  a,
  top,
  left,
  onOpenInPanel,
}: {
  a: Annotation;
  top: number;
  left: number;
  onOpenInPanel: () => void;
}) {
  return (
    <div
      className="annot-peek"
      role="dialog"
      aria-label={`Note on "${a.match}"`}
      style={{ top, left }}
    >
      <div className="annot-peek-head">
        <span>Your note · {a.created_at}</span>
        <span className="annot-private-chip">
          <IcPrivate size={8} /> private
        </span>
      </div>
      <div className="annot-peek-body" style={{ fontStyle: "italic" }}>
        {a.body ?? ""}
      </div>
      {a.tags && a.tags.length > 0 && (
        <div style={{ padding: "0 14px 10px", display: "flex", gap: 4 }}>
          {a.tags.map((t) => (
            <span key={t} className="annot-tag">
              {t}
            </span>
          ))}
        </div>
      )}
      <div className="annot-peek-foot">
        <button type="button" className="annot-peek-action">
          <IcEdit size={11} /> Edit
        </button>
        <button type="button" className="annot-peek-action" onClick={onOpenInPanel}>
          <IcExpand size={11} /> Open in panel
        </button>
      </div>
    </div>
  );
}

function QueryPeekBody({
  a,
  top,
  left,
  onOpenInPanel,
}: {
  a: Annotation;
  top: number;
  left: number;
  onOpenInPanel: () => void;
}) {
  return (
    <div
      className="annot-peek"
      role="dialog"
      aria-label={`Question about "${a.match}"`}
      style={{ top, left }}
    >
      <div className="annot-peek-head">
        <span>Question · 1 answer</span>
        {a.bookmarked && <IcBookmark size={11} style={{ color: "var(--accent)" }} />}
      </div>
      <div style={{ padding: "4px 14px 10px" }}>
        <div
          style={{
            fontFamily: "var(--serif)",
            fontSize: 13,
            color: "var(--ink-0)",
            marginBottom: 8,
            fontWeight: 500,
          }}
        >
          {a.question ?? ""}
        </div>
        <div
          style={{
            fontFamily: "var(--serif)",
            fontSize: 12.5,
            lineHeight: 1.5,
            color: "var(--ink-2)",
            fontStyle: "italic",
          }}
        >
          {a.answer_excerpt ?? ""}
        </div>
      </div>
      <div className="annot-peek-foot">
        <span
          style={{
            fontSize: 10.5,
            color: "var(--ink-3)",
            fontFamily: "var(--mono)",
          }}
        >
          spoiler-safe
        </span>
        <button type="button" className="annot-peek-action" onClick={onOpenInPanel}>
          <IcExpand size={11} /> Open thread
        </button>
      </div>
    </div>
  );
}
