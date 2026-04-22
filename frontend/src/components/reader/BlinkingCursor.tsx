export function BlinkingCursor() {
  return (
    <span
      data-testid="blinking-cursor"
      style={{
        display: "inline-block",
        width: "6px",
        height: "14px",
        background: "var(--ink-2)",
        verticalAlign: "middle",
        marginLeft: 2,
        animation: "blink 1s infinite",
      }}
    />
  );
}
