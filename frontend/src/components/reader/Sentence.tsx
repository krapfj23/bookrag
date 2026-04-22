import type { CSSProperties } from "react";

export type SentenceMark = { kind: "ask" | "note"; cardId: string };

export function Sentence({
  sid,
  text,
  fogged,
  marks = [],
  onMarkClick,
}: {
  sid: string;
  text: string;
  fogged: boolean;
  marks?: SentenceMark[];
  onMarkClick?: (cardId: string) => void;
}) {
  const asked = marks.find((m) => m.kind === "ask");
  const noted = marks.find((m) => m.kind === "note");
  const style: CSSProperties = {
    transition: "opacity 180ms ease, filter 180ms ease",
    opacity: fogged ? 0.3 : 1,
    filter: fogged ? "blur(2.2px)" : "blur(0)",
    cursor: (asked || noted) && onMarkClick ? "pointer" : "inherit",
  };
  if (asked) {
    style.background = "oklch(72% 0.08 155 / 0.42)";
    style.padding = "1px 3px";
    style.borderRadius = 2;
  }
  if (noted) {
    style.textDecoration = "underline";
    style.textDecorationColor = "oklch(58% 0.1 55)";
    style.textDecorationThickness = "1.5px";
    style.textUnderlineOffset = "3px";
  }
  const onClick =
    onMarkClick && (asked || noted)
      ? () => onMarkClick((asked ?? noted)!.cardId)
      : undefined;
  return (
    <span data-sid={sid} data-kind={noted ? "note" : undefined} style={style} onClick={onClick}>
      {text}
    </span>
  );
}
