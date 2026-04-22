import { useState } from "react";
import { IcArrowL, IcArrowR } from "../icons";

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
  const [hovered, setHovered] = useState(false);

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
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      style={{
        position: "fixed",
        top: "50%",
        [direction === "left" ? "left" : "right"]: 16,
        transform: "translateY(-50%)",
        background: "var(--paper-1, rgba(255,255,255,0.8))",
        border: 0,
        borderRadius: "999px",
        width: "48px",
        height: "48px",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        color: disabled ? "var(--ink-4, #ccc)" : "var(--ink-1, #333)",
        cursor: disabled ? "not-allowed" : "pointer",
        opacity: disabled ? 0.25 : hovered ? 1 : 0.5,
        transition: "opacity 180ms ease",
        userSelect: "none",
        zIndex: 100,
      }}
    >
      {direction === "left" ? <IcArrowL size={18} /> : <IcArrowR size={18} />}
    </button>
  );
}
