function relativeTime(createdAt: string): string {
  if (!createdAt) return "just now";
  const now = Date.now();
  const then = new Date(createdAt).getTime();
  if (Number.isNaN(then)) return "just now";
  const diffMs = now - then;
  const diffMin = Math.floor(diffMs / 60_000);
  const diffHr = Math.floor(diffMs / 3_600_000);
  const diffDay = Math.floor(diffMs / 86_400_000);
  if (diffMin < 1) return "just now";
  if (diffMin < 60) return `${diffMin} min ago`;
  if (diffHr < 24) return `${diffHr} hr ago`;
  return `${diffDay} day${diffDay !== 1 ? "s" : ""} ago`;
}

export function NotePeekPopover({
  visible,
  body,
  x,
  y,
  createdAt = "",
}: {
  visible: boolean;
  body: string;
  x: number;
  y: number;
  createdAt?: string;
}) {
  if (!visible) return null;

  return (
    <div
      data-testid="note-peek"
      style={{
        position: "fixed",
        left: x,
        top: y,
        transform: "translate(-50%, -100%) translateY(-8px)",
        background: "var(--paper-00)",
        border: "1px solid var(--paper-2)",
        borderLeft: "3px solid oklch(58% 0.1 55)",
        borderRadius: "10px",
        padding: "12px 16px",
        width: "360px",
        fontSize: 13,
        fontFamily: "var(--serif)",
        color: "var(--ink-1)",
        boxShadow: "0 20px 40px -12px rgba(28,24,18,.2)",
        zIndex: 200,
        pointerEvents: "none",
      }}
    >
      <div>{body}</div>
      <div
        style={{
          fontFamily: "var(--sans)",
          fontSize: 10.5,
          color: "var(--ink-3)",
          marginTop: 6,
        }}
      >
        {relativeTime(createdAt)}
      </div>
    </div>
  );
}
