export function AnchorConnector({
  from,
  to,
}: {
  from: { x: number; y: number };
  to: { x: number; y: number };
}) {
  // Compute a quadratic Bezier control point for a smooth curve.
  const cx = from.x + (to.x - from.x) * 0.5;
  const cy = from.y;
  const d = `M ${from.x} ${from.y} Q ${cx} ${cy} ${to.x} ${to.y}`;

  return (
    <svg
      data-testid="anchor-connector"
      style={{
        position: "absolute",
        top: 0,
        left: 0,
        width: "100%",
        height: "100%",
        pointerEvents: "none",
        overflow: "visible",
      }}
    >
      <path
        d={d}
        fill="none"
        stroke="var(--accent)"
        strokeOpacity={0.6}
        strokeWidth={1.5}
        strokeDasharray="4 3"
      />
    </svg>
  );
}
