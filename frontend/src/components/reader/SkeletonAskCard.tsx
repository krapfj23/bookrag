export function SkeletonAskCard() {
  return (
    <article
      data-testid="skeleton-ask-card"
      style={{
        background: "var(--paper-00)",
        border: "1px solid var(--paper-2)",
        borderLeft: "3px solid var(--accent)",
        borderRadius: 10,
        padding: "14px 16px",
        boxShadow: "0 4px 12px -4px rgba(28,24,18,.08)",
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
          marginBottom: 10,
        }}
      >
        THINKING · gathering 3 more passages
      </header>
      <div
        data-testid="skeleton-shimmer"
        style={{
          height: 12,
          borderRadius: 4,
          background: "var(--paper-2)",
          opacity: 0.6,
          marginBottom: 8,
          animation: "shimmer 1.4s ease-in-out infinite",
        }}
      />
      <div
        data-testid="skeleton-shimmer"
        style={{
          height: 12,
          borderRadius: 4,
          background: "var(--paper-2)",
          opacity: 0.4,
          width: "70%",
          animation: "shimmer 1.4s ease-in-out 0.2s infinite",
        }}
      />
    </article>
  );
}
