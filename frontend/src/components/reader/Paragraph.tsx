import { Sentence, type SentenceMark } from "./Sentence";
import type { AnchoredSentence, ParagraphKind } from "../../lib/api";
import { compareSid } from "../../lib/reader/sidCompare";

export function Paragraph({
  paragraphIdx,
  sentences,
  fogStartSid,
  dropCap,
  kind = "body",
  marksBySid,
  onMarkClick,
}: {
  paragraphIdx: number;
  sentences: AnchoredSentence[];
  fogStartSid: string | null;
  dropCap: boolean;
  kind?: ParagraphKind;
  marksBySid?: Map<string, SentenceMark[]>;
  onMarkClick?: (cardId: string) => void;
}) {
  if (kind === "scene_break") {
    // Ornamental dinkus — non-interactive, centered, not a drop cap target.
    // Keeps sentence markup so the sid is still anchorable for cards.
    const s = sentences[0];
    return (
      <p
        aria-hidden="true"
        data-paragraph-idx={paragraphIdx}
        className="rr-para rr-scene-break"
      >
        <span data-sid={s?.sid ?? `p${paragraphIdx}.s1`}>* * *</span>
      </p>
    );
  }

  const baseClass =
    kind === "epigraph"
      ? "rr-para rr-epigraph"
      : dropCap
      ? "rr-para rr-dropcap"
      : "rr-para";

  return (
    <p
      data-paragraph-idx={paragraphIdx}
      className={baseClass}
      style={{ margin: "0 0 0.9em", textAlign: "justify", hyphens: "auto" }}
    >
      {sentences.map((s, i) => {
        const fogged = fogStartSid !== null && compareSid(s.sid, fogStartSid) > 0;
        return (
          <span key={s.sid}>
            <Sentence
              sid={s.sid}
              text={s.text}
              fogged={fogged}
              marks={marksBySid?.get(s.sid) ?? []}
              onMarkClick={onMarkClick}
            />
            {i < sentences.length - 1 ? " " : ""}
          </span>
        );
      })}
    </p>
  );
}
