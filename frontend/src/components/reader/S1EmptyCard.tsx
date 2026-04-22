export function S1EmptyCard() {
  return (
    <article
      data-testid="s1-empty-card"
      style={{
        background: "var(--paper-00)",
        border: "1px solid var(--paper-2)",
        borderRadius: 10,
        padding: "18px 18px 16px",
        boxShadow: "0 4px 12px -4px rgba(28,24,18,.06)",
        display: "grid",
        gridTemplateColumns: "34px 1fr",
        gap: 12,
      }}
    >
      <div
        aria-hidden="true"
        style={{
          width: 34,
          height: 34,
          borderRadius: 999,
          background: "var(--accent-softer)",
          display: "grid",
          placeItems: "center",
          color: "var(--accent-ink)",
          fontSize: 16,
        }}
      >
        ✦
      </div>
      <div>
        <h3
          style={{
            fontFamily: "var(--serif)",
            fontWeight: 500,
            fontSize: 15,
            margin: "2px 0 4px",
            color: "var(--ink-0)",
          }}
        >
          Ask about what you're reading
        </h3>
        <p
          style={{
            fontFamily: "var(--sans)",
            fontSize: 12,
            color: "var(--ink-2)",
            margin: 0,
            lineHeight: 1.5,
          }}
        >
          Select a phrase to Ask, Note, or Highlight.
        </p>
      </div>
    </article>
  );
}
