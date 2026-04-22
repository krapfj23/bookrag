function clamp(value: number, min: number, max: number): number {
  return Math.min(Math.max(value, min), max);
}

export function ProgressHairline({ progress }: { progress: number }) {
  const clamped = clamp(progress, 0, 1);
  const pct = Math.round(clamped * 10000) / 100 + "%";

  return (
    <div
      data-testid="progress-hairline"
      style={{
        position: "fixed",
        bottom: 0,
        left: 0,
        right: 0,
        height: 3,
        background: "var(--paper-2)",
        zIndex: 100,
      }}
    >
      <div
        style={{
          height: "100%",
          width: pct,
          background: "var(--accent, oklch(55% 0.18 155))",
          transition: "width 300ms ease",
        }}
      />
    </div>
  );
}
