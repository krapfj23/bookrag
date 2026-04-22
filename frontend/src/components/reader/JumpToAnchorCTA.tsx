export function JumpToAnchorCTA({ onJump }: { onJump: () => void }) {
  return (
    <button
      type="button"
      data-testid="jump-to-anchor-cta"
      onClick={onJump}
      style={{
        display: "block",
        marginTop: 10,
        width: "100%",
        padding: "6px 10px",
        background: "var(--accent-softer)",
        border: "1px dashed var(--accent)",
        borderRadius: 6,
        fontFamily: "var(--sans)",
        fontSize: 11,
        color: "var(--accent-ink)",
        cursor: "pointer",
        textAlign: "left",
      }}
    >
      Jump to anchor on this page
    </button>
  );
}
