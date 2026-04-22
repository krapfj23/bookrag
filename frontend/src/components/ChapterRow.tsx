import type { CSSProperties } from "react";
import { IcDot, IcCheck, IcLock } from "./icons";

export type ChapterRowState = "read" | "current" | "locked";

type ChapterRowProps = {
  num: number;
  title: string;
  state: ChapterRowState;
  onClick?: () => void;
};

export function ChapterRow({ num, title, state, onClick }: ChapterRowProps) {
  const isLocked = state === "locked";
  const isCurrent = state === "current";
  const isRead = state === "read";

  const rootStyle: CSSProperties = {
    display: "grid",
    gridTemplateColumns: "42px 1fr auto",
    alignItems: "center",
    gap: 14,
    padding: "14px 20px",
    width: "100%",
    textAlign: "left",
    border: 0,
    borderBottom: "var(--hairline)",
    fontFamily: "var(--sans)",
    background: isCurrent ? "var(--accent-softer)" : "transparent",
    color: isLocked ? "var(--ink-3)" : "var(--ink-1)",
    cursor: isLocked ? "not-allowed" : "pointer",
    transition: "background var(--dur) var(--ease)",
  };

  return (
    <button
      type="button"
      role="button"
      onClick={() => {
        if (!isLocked) onClick?.();
      }}
      aria-current={isCurrent ? "true" : undefined}
      aria-disabled={isLocked ? "true" : undefined}
      data-state={state}
      style={rootStyle}
    >
      <span
        style={{
          fontFamily: "var(--serif)",
          fontStyle: "italic",
          fontSize: 14,
          color: isCurrent
            ? "var(--accent)"
            : isLocked
              ? "var(--ink-4)"
              : "var(--ink-3)",
          fontVariantNumeric: "tabular-nums",
          letterSpacing: 0.3,
        }}
      >
        {num.toString().padStart(2, "0")}
      </span>
      <span
        style={{
          fontFamily: "var(--serif)",
          fontSize: 16,
          fontWeight: isCurrent ? 500 : 400,
          color: isLocked ? "var(--ink-3)" : isRead ? "var(--ink-2)" : "var(--ink-0)",
          letterSpacing: -0.2,
        }}
      >
        {title}
      </span>
      <span style={{ width: 20, display: "inline-flex", justifyContent: "flex-end" }}>
        {isCurrent && (
          <span style={{ color: "var(--accent)" }}>
            <IcDot size={10} />
          </span>
        )}
        {isRead && (
          <span style={{ color: "var(--ink-3)" }}>
            <IcCheck size={13} />
          </span>
        )}
        {isLocked && (
          <span style={{ color: "var(--ink-4)" }}>
            <IcLock size={13} />
          </span>
        )}
      </span>
    </button>
  );
}
