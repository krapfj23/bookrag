import type { Card } from "../../lib/reader/cards";
import { getFolioFromAnchor } from "../../lib/reader/overflow";

export function CollapsedCardRow({
  card,
  onExpand,
}: {
  card: Card;
  onExpand: (id: string) => void;
}) {
  const folio = getFolioFromAnchor(card.anchor);
  const label =
    card.kind === "ask" ? card.question : card.body.split("\n")[0];
  const borderColor =
    card.kind === "ask" ? "var(--accent)" : "oklch(58% 0.1 55)";

  return (
    <button
      type="button"
      data-testid="collapsed-card-row"
      onClick={() => onExpand(card.id)}
      style={{
        display: "flex",
        alignItems: "center",
        gap: 6,
        width: "100%",
        padding: "8px 12px",
        borderRadius: 8,
        border: "1px solid var(--paper-2)",
        borderLeft: `3px solid ${borderColor}`,
        background: "var(--paper-00)",
        cursor: "pointer",
        textAlign: "left",
        fontFamily: "var(--sans)",
        fontSize: 12,
        color: "var(--ink-1)",
      }}
    >
      <span style={{ flexShrink: 0 }}>p.{folio}</span>
      <span style={{ margin: "0 2px" }}>·</span>
      <span
        style={{
          fontStyle: "italic",
          overflow: "hidden",
          textOverflow: "ellipsis",
          whiteSpace: "nowrap",
          flex: 1,
        }}
      >
        {label}
      </span>
      <span style={{ flexShrink: 0 }}>·</span>
      <span style={{ flexShrink: 0 }}>›</span>
    </button>
  );
}
