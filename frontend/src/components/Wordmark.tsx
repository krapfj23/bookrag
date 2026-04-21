export function Wordmark({ size = 20 }: { size?: number }) {
  return (
    <span
      style={{
        fontFamily: "var(--serif)",
        fontSize: size,
        fontWeight: 500,
        letterSpacing: -0.3,
        color: "var(--ink-0)",
      }}
    >
      Book
      <span style={{ fontStyle: "italic", color: "var(--accent)" }}>rag</span>
    </span>
  );
}
