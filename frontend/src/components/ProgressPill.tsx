type ProgressPillProps = {
  current: number;
  total: number;
  variant?: "default" | "soft";
};

export function ProgressPill({
  current,
  total,
  variant = "default",
}: ProgressPillProps) {
  const safeTotal = Math.max(1, total);
  const pct = Math.min(100, Math.max(0, (current / safeTotal) * 100));
  const isSoft = variant === "soft";
  return (
    <div
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: 8,
        height: 28,
        padding: "0 12px",
        borderRadius: "var(--r-pill)",
        background: isSoft ? "var(--accent-softer)" : "var(--paper-1)",
        color: isSoft ? "var(--accent-ink)" : "var(--ink-1)",
        fontFamily: "var(--sans)",
        fontSize: 12,
        fontWeight: 500,
        fontVariantNumeric: "tabular-nums",
        letterSpacing: 0.2,
      }}
    >
      <span>{current}</span>
      <span
        style={{
          flexShrink: 0,
          width: 36,
          height: 3,
          borderRadius: 999,
          background: isSoft
            ? "color-mix(in oklab, var(--accent) 20%, transparent)"
            : "var(--paper-3)",
          position: "relative",
          overflow: "hidden",
        }}
      >
        <div
          data-pill-fill
          style={{
            position: "absolute",
            inset: 0,
            width: `${pct}%`,
            background: isSoft ? "var(--accent)" : "var(--ink-2)",
            transition: "width var(--dur-slow) var(--ease-out)",
          }}
        />
      </span>
      <span style={{ opacity: 0.6 }}>of {total}</span>
    </div>
  );
}
