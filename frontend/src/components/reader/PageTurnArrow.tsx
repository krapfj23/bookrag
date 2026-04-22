export function PageTurnArrow({
  direction,
  onClick,
  disabled = false,
}: {
  direction: "left" | "right";
  onClick: () => void;
  disabled?: boolean;
}) {
  const testId = direction === "left" ? "page-arrow-left" : "page-arrow-right";
  const label = direction === "left" ? "Previous page" : "Next page";
  const symbol = direction === "left" ? "←" : "→";

  function handleClick() {
    if (!disabled) onClick();
  }

  return (
    <button
      type="button"
      data-testid={testId}
      aria-label={label}
      aria-disabled={disabled ? "true" : undefined}
      onClick={handleClick}
      style={{
        position: "fixed",
        top: "50%",
        [direction === "left" ? "left" : "right"]: 16,
        transform: "translateY(-50%)",
        background: "var(--paper-1, rgba(255,255,255,0.8))",
        border: "1px solid var(--ink-4, rgba(0,0,0,0.15))",
        borderRadius: 8,
        width: 40,
        height: 40,
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        fontSize: 18,
        color: disabled ? "var(--ink-4, #ccc)" : "var(--ink-1, #333)",
        cursor: disabled ? "not-allowed" : "pointer",
        opacity: disabled ? 0.4 : 1,
        transition: "opacity 180ms ease",
        userSelect: "none",
        zIndex: 100,
      }}
    >
      {symbol}
    </button>
  );
}
