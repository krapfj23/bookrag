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
      className="selection-toolbar"
      style={{ top, left }}
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
      <span aria-hidden="true" className="selection-toolbar-arrow" />
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
      className="selection-toolbar-btn"
    >
      {children}
    </button>
  );
}
