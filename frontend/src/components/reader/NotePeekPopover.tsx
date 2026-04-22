export function NotePeekPopover({
  visible,
  body,
  x,
  y,
}: {
  visible: boolean;
  body: string;
  x: number;
  y: number;
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
        background: "var(--paper-0, #fff)",
        border: "1px solid var(--ink-3, rgba(0,0,0,0.2))",
        borderRadius: 8,
        padding: "8px 12px",
        maxWidth: 280,
        fontSize: 13,
        fontFamily: "var(--serif)",
        color: "var(--ink-1)",
        boxShadow: "0 4px 16px rgba(0,0,0,0.12)",
        zIndex: 200,
        pointerEvents: "none",
      }}
    >
      {body}
    </div>
  );
}
