import type { CSSProperties } from "react";

export function Sentence({
  sid,
  text,
  fogged,
}: {
  sid: string;
  text: string;
  fogged: boolean;
}) {
  const style: CSSProperties = fogged
    ? { opacity: 0.3, filter: "blur(2.2px)", transition: "opacity 180ms ease, filter 180ms ease" }
    : { opacity: 1, filter: "blur(0)", transition: "opacity 180ms ease, filter 180ms ease" };
  return (
    <span data-sid={sid} style={style}>
      {text}
    </span>
  );
}
