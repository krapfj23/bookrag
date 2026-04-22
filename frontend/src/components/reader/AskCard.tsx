import type { AskCard as AskCardT } from "../../lib/reader/cards";

export function AskCard({
  card,
  flash,
}: {
  card: AskCardT;
  flash: boolean;
}) {
  return (
    <article
      data-card-id={card.id}
      data-card-kind="ask"
      data-card-anchor={card.anchor}
      className={flash ? "rr-card rr-card-flash" : "rr-card"}
      style={{
        background: "var(--paper-00)",
        border: "1px solid var(--paper-2)",
        borderLeft: "3px solid var(--accent)",
        borderRadius: 10,
        padding: "14px 16px",
        boxShadow: "0 4px 12px -4px rgba(28,24,18,.08)",
        transform: "rotate(-0.2deg)",
        fontFamily: "var(--serif)",
      }}
    >
      <header
        style={{
          fontFamily: "var(--sans)",
          fontSize: 9.5,
          letterSpacing: 1.3,
          textTransform: "uppercase",
          color: "var(--accent-ink)",
          fontWeight: 600,
          marginBottom: 6,
        }}
      >
        ASKED ABOUT "{card.quote}"
      </header>
      <div
        style={{
          fontStyle: "italic",
          fontSize: 13.5,
          color: "var(--ink-1)",
          marginBottom: 6,
        }}
      >
        {card.question}
      </div>
      <div
        data-testid="ask-answer"
        style={{ fontSize: 14, lineHeight: 1.62, color: "var(--ink-0)" }}
      >
        {card.answer}
      </div>
    </article>
  );
}
