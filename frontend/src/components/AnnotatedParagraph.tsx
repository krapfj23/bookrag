import type { Annotation } from "../lib/annotations";

interface Props {
  text: string;
  annotations: Annotation[]; // all annotations whose paragraph_index matches this paragraph
  activeId?: string;
  onAnnotationClick?: (annotation: Annotation) => void;
  // Per-paragraph fog level (1–5) when the paragraph is BELOW the cutoff.
  // If omitted, no fog applies.
  fogLevel?: 0 | 1 | 2 | 3 | 4 | 5;
  // When this paragraph CONTAINS the cutoff, split text at this char offset:
  // everything before is legible; everything after gets fog-1.
  cutoffCharOffset?: number;
}

// Splits paragraph text into plain text + annotated spans at each match.
// If an annotation's `match` substring doesn't occur in `text`, it is skipped.
// Also supports mid-paragraph fog split at `cutoffCharOffset`.
export function AnnotatedParagraph({
  text,
  annotations,
  activeId,
  onAnnotationClick,
  fogLevel = 0,
  cutoffCharOffset,
}: Props) {
  // If this paragraph is below the cutoff (fogLevel > 0) and has no mid-split
  // offset, just blur the whole paragraph as one wrapped span.
  if (fogLevel > 0 && cutoffCharOffset === undefined) {
    return (
      <span className={`fog fog-${fogLevel}`}>
        {renderAnnotated(text, annotations, activeId, onAnnotationClick)}
      </span>
    );
  }

  // If the cutoff falls INSIDE this paragraph, split into a clear "before"
  // segment and a blurred "after" segment. Annotations are still rendered
  // in the before segment (including spans that straddle the boundary —
  // we truncate them at the cutoff for visual clarity).
  if (cutoffCharOffset !== undefined) {
    const boundary = Math.max(0, Math.min(text.length, cutoffCharOffset));
    const beforeText = text.slice(0, boundary);
    const afterText = text.slice(boundary);
    const beforeAnnots = annotations.filter((a) => {
      const s = text.indexOf(a.match);
      return s >= 0 && s < boundary;
    });
    return (
      <>
        {renderAnnotated(beforeText, beforeAnnots, activeId, onAnnotationClick)}
        {afterText.length > 0 && <span className="fog fog-1">{afterText}</span>}
      </>
    );
  }

  return <>{renderAnnotated(text, annotations, activeId, onAnnotationClick)}</>;
}

function renderAnnotated(
  text: string,
  annotations: Annotation[],
  activeId: string | undefined,
  onClick: ((a: Annotation) => void) | undefined,
): React.ReactNode {
  if (annotations.length === 0) return text;

  type Range = { annotation: Annotation; start: number; end: number };
  const ranges: Range[] = [];
  for (const a of annotations) {
    const start = text.indexOf(a.match);
    if (start < 0) continue;
    ranges.push({ annotation: a, start, end: start + a.match.length });
  }
  ranges.sort((a, b) => a.start - b.start);

  const safe: Range[] = [];
  let cursor = 0;
  for (const r of ranges) {
    if (r.start < cursor) continue;
    safe.push(r);
    cursor = r.end;
  }

  const out: (string | JSX.Element)[] = [];
  let pos = 0;
  for (const r of safe) {
    if (r.start > pos) out.push(text.slice(pos, r.start));
    const { annotation } = r;
    const cls = annotation.kind === "note" ? "annot-note" : "annot-query";
    const isActive = annotation.id === activeId;
    out.push(
      <span
        key={annotation.id}
        className={isActive ? `${cls} active` : cls}
        role="button"
        tabIndex={0}
        data-annotation-id={annotation.id}
        data-annotation-kind={annotation.kind}
        onClick={() => onClick?.(annotation)}
        onKeyDown={(e) => {
          if (e.key === "Enter" || e.key === " ") {
            e.preventDefault();
            onClick?.(annotation);
          }
        }}
      >
        {text.slice(r.start, r.end)}
      </span>,
    );
    pos = r.end;
  }
  if (pos < text.length) out.push(text.slice(pos));
  return out;
}

// Map a paragraph's distance below the cutoff paragraph to a fog level.
// Paragraph N+1 → fog-1, N+2 → fog-2, … N+5+ → fog-5 (cap).
export function fogLevelFor(distance: number): 0 | 1 | 2 | 3 | 4 | 5 {
  if (distance <= 0) return 0;
  if (distance >= 5) return 5;
  return distance as 1 | 2 | 3 | 4;
}
