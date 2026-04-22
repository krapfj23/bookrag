import type { CSSProperties } from "react";

export type SelectionAction = "ask" | "note" | "highlight";

interface Props {
  top: number;
  left: number;
  onAction: (action: SelectionAction) => void;
  disabled?: Partial<Record<SelectionAction, boolean>>;
}

const pillStyle: CSSProperties = {
  position: "fixed",
  display: "inline-flex",
  alignItems: "center",
  gap: 2,
  height: 32,
  padding: "0 4px",
  borderRadius: 999,
  background: "var(--ink-0)",
  color: "var(--paper-00)",
  boxShadow: "0 4px 16px -4px rgba(28,24,18,.35)",
  fontFamily: "var(--sans)",
  fontSize: 12,
  letterSpacing: 0.2,
  zIndex: 50,
  transform: "translate(-50%, -100%) translateY(-6px)",
  opacity: 1,
  transition: "opacity 180ms ease, transform 180ms ease",
  userSelect: "none",
};

const btnStyle = (disabled: boolean): CSSProperties => ({
  height: 26,
  padding: "0 10px",
  borderRadius: 999,
  background: "transparent",
  color: disabled ? "color-mix(in oklab, var(--paper-00) 45%, transparent)" : "var(--paper-00)",
  border: 0,
  cursor: disabled ? "not-allowed" : "pointer",
  fontFamily: "var(--sans)",
  fontSize: 12,
});

export function SelectionToolbar({ top, left, onAction, disabled = {} }: Props) {
  const askDisabled = !!disabled.ask;
  const noteDisabled = !!disabled.note;
  const hlDisabled = !!disabled.highlight;
  return (
    <div
      role="toolbar"
      aria-label="Selection actions"
      data-testid="selection-toolbar"
      style={{ ...pillStyle, top, left }}
      onMouseDown={(e) => e.preventDefault()}
    >
      <button
        type="button"
        aria-label="Ask"
        disabled={askDisabled}
        title={askDisabled ? "Reach this sentence first" : "Ask a question"}
        onClick={() => !askDisabled && onAction("ask")}
        style={btnStyle(askDisabled)}
      >
        Ask
      </button>
      <button
        type="button"
        aria-label="Note"
        disabled={noteDisabled}
        title="Add a note"
        onClick={() => !noteDisabled && onAction("note")}
        style={btnStyle(noteDisabled)}
      >
        Note
      </button>
      <button
        type="button"
        aria-label="Highlight"
        disabled={hlDisabled}
        title="Highlight passage"
        onClick={() => !hlDisabled && onAction("highlight")}
        style={btnStyle(hlDisabled)}
      >
        Highlight
      </button>
    </div>
  );
}
