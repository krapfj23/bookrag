import { IcChat, IcEdit, IcHighlight } from "./icons";

export type SelectionAction = "ask" | "note" | "highlight";

interface Props {
  // Position in viewport pixels. The toolbar renders as a position:fixed
  // element so the reading column's scrolling doesn't displace it.
  top: number;
  left: number;
  onAction: (action: SelectionAction) => void;
}

export function SelectionToolbar({ top, left, onAction }: Props) {
  return (
    <div
      role="toolbar"
      aria-label="Selection actions"
      style={{
        position: "fixed",
        top,
        left,
        transform: "translate(-50%, -100%) translateY(-10px)",
        background: "var(--paper-00)",
        border: "1px solid var(--paper-2)",
        borderRadius: "var(--r-lg)",
        boxShadow: "0 10px 28px rgba(32,28,22,0.14), 0 1px 3px rgba(0,0,0,0.04)",
        padding: 4,
        display: "inline-flex",
        gap: 2,
        zIndex: 20,
        fontFamily: "var(--sans)",
        animation: "annot-fadeUp 140ms var(--ease-out)",
      }}
      // Prevent the toolbar's mousedown from collapsing the selection
      // before our click handler fires.
      onMouseDown={(e) => e.preventDefault()}
    >
      <ToolbarButton
        label="Ask a question"
        shortcut="⏎"
        onClick={() => onAction("ask")}
      >
        <IcChat size={13} /> Ask
      </ToolbarButton>
      <ToolbarButton label="Add a note" shortcut="N" onClick={() => onAction("note")}>
        <IcEdit size={13} /> Note
      </ToolbarButton>
      <ToolbarButton
        label="Highlight passage"
        shortcut="H"
        onClick={() => onAction("highlight")}
      >
        <IcHighlight size={13} /> Highlight
      </ToolbarButton>
      <Arrow />
    </div>
  );
}

function ToolbarButton({
  children,
  label,
  shortcut,
  onClick,
}: {
  children: React.ReactNode;
  label: string;
  shortcut: string;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      aria-label={label}
      title={`${label} (${shortcut})`}
      onClick={onClick}
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: 5,
        padding: "6px 10px",
        background: "transparent",
        border: 0,
        borderRadius: "var(--r-md)",
        color: "var(--ink-1)",
        fontFamily: "var(--sans)",
        fontSize: 12,
        fontWeight: 500,
        cursor: "pointer",
        transition: "background var(--dur)",
      }}
      onMouseOver={(e) => {
        e.currentTarget.style.background = "var(--paper-1)";
      }}
      onMouseOut={(e) => {
        e.currentTarget.style.background = "transparent";
      }}
    >
      {children}
    </button>
  );
}

function Arrow() {
  return (
    <span
      aria-hidden="true"
      style={{
        position: "absolute",
        bottom: -5,
        left: "50%",
        transform: "translateX(-50%) rotate(45deg)",
        width: 9,
        height: 9,
        background: "var(--paper-00)",
        borderRight: "1px solid var(--paper-2)",
        borderBottom: "1px solid var(--paper-2)",
      }}
    />
  );
}
