import type { ReadingMode } from "../../lib/reader/useReadingMode";

export function ReadingModeToggle({
  mode,
  onToggle,
}: {
  mode: ReadingMode;
  onToggle: () => void;
}) {
  const isOn = mode === "on";
  return (
    <button
      type="button"
      aria-label="Reading mode"
      data-state={mode}
      onClick={onToggle}
      style={{
        fontFamily: "var(--sans)",
        fontSize: 12,
        fontWeight: 500,
        padding: "4px 12px",
        borderRadius: 20,
        border: isOn ? "1.5px solid var(--ink-0)" : "1.5px solid var(--ink-3)",
        background: isOn ? "var(--ink-0)" : "var(--paper-1)",
        color: isOn ? "var(--paper-0)" : "var(--ink-1)",
        cursor: "pointer",
        transition: "background 200ms ease, color 200ms ease, border-color 200ms ease",
        userSelect: "none",
      }}
    >
      {isOn ? "✓ Reading" : "Reading mode"}
    </button>
  );
}
