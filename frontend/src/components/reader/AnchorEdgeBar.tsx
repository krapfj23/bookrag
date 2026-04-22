export function AnchorEdgeBar({
  top,
  color,
}: {
  top: number;
  color: string;
}) {
  return (
    <div
      data-testid="anchor-edge-bar"
      style={{
        position: "absolute",
        top: `${top}px`,
        right: 0,
        width: "3px",
        height: 40,
        background: color,
        borderRadius: 2,
        pointerEvents: "none",
      }}
    />
  );
}
