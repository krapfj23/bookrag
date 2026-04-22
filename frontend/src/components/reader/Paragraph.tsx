import { Sentence } from "./Sentence";
import type { AnchoredSentence } from "../../lib/api";
import { compareSid } from "../../lib/reader/sidCompare";

export function Paragraph({
  paragraphIdx,
  sentences,
  fogStartSid,
  dropCap,
}: {
  paragraphIdx: number;
  sentences: AnchoredSentence[];
  fogStartSid: string | null;
  dropCap: boolean;
}) {
  return (
    <p
      data-paragraph-idx={paragraphIdx}
      className={dropCap ? "rr-para rr-dropcap" : "rr-para"}
      style={{ margin: "0 0 0.9em", textAlign: "justify", hyphens: "auto" }}
    >
      {sentences.map((s, i) => {
        const fogged = fogStartSid !== null && compareSid(s.sid, fogStartSid) > 0;
        return (
          <span key={s.sid}>
            <Sentence sid={s.sid} text={s.text} fogged={fogged} />
            {i < sentences.length - 1 ? " " : ""}
          </span>
        );
      })}
    </p>
  );
}
