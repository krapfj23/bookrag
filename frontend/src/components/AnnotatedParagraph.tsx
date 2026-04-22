import type { Annotation } from "../lib/annotations";

interface Props {
  text: string;
  annotations: Annotation[]; // all annotations whose paragraph_index matches this paragraph
  activeId?: string;
  onAnnotationClick?: (annotation: Annotation) => void;
}

// Splits paragraph text into plain text + annotated spans at each match.
// If an annotation's `match` substring doesn't occur in `text`, it is skipped
// silently — seed data matches prose verbatim, but a missing match should
// never crash the reader.
export function AnnotatedParagraph({
  text,
  annotations,
  activeId,
  onAnnotationClick,
}: Props) {
  if (annotations.length === 0) {
    return <>{text}</>;
  }

  // Resolve each annotation's start/end offsets within this paragraph. Sort
  // by start so we can walk left-to-right and emit alternating plain/span
  // segments. Overlapping annotations are not supported in the seed set;
  // if two ranges overlap, the later one is dropped to keep the walk safe.
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
    if (r.start < cursor) continue; // overlap with a previous annotation
    safe.push(r);
    cursor = r.end;
  }

  const out: (string | JSX.Element)[] = [];
  let pos = 0;
  for (const r of safe) {
    if (r.start > pos) out.push(text.slice(pos, r.start));
    const { annotation } = r;
    const cls =
      annotation.kind === "note" ? "annot-note" : "annot-query";
    const isActive = annotation.id === activeId;
    out.push(
      <span
        key={annotation.id}
        className={isActive ? `${cls} active` : cls}
        role="button"
        tabIndex={0}
        data-annotation-id={annotation.id}
        data-annotation-kind={annotation.kind}
        onClick={() => onAnnotationClick?.(annotation)}
        onKeyDown={(e) => {
          if (e.key === "Enter" || e.key === " ") {
            e.preventDefault();
            onAnnotationClick?.(annotation);
          }
        }}
      >
        {text.slice(r.start, r.end)}
      </span>,
    );
    pos = r.end;
  }
  if (pos < text.length) out.push(text.slice(pos));

  return <>{out}</>;
}
