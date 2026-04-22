import type { PanelTab } from "./AnnotationPanel";
import { IcArrowL, IcEdit, IcHighlight, IcSpark } from "./icons";

interface Props {
  onOpen: (tab: PanelTab) => void;
  // Which tabs currently have unseen activity (shows pip indicator).
  pips?: Partial<Record<PanelTab, boolean>>;
}

// 48-pixel collapsed rail. Sits where the old chat aside used to live.
// Clicking a button asks the parent to expand the panel to that tab.
export function AnnotationRail({ onOpen, pips = {} }: Props) {
  return (
    <aside
      aria-label="Annotations rail"
      style={{
        width: 48,
        borderLeft: "var(--hairline)",
        background:
          "color-mix(in oklab, var(--paper-0) 94%, var(--paper-1))",
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        padding: "14px 0",
      }}
    >
      <RailButton
        label="Thread"
        pip={pips.thread}
        onClick={() => onOpen("thread")}
      >
        <IcSpark size={14} />
      </RailButton>
      <RailButton
        label="Notes"
        pip={pips.notes}
        pipDark
        onClick={() => onOpen("notes")}
      >
        <IcEdit size={14} />
      </RailButton>
      <RailButton
        label="Highlights"
        pip={pips.highlights}
        onClick={() => onOpen("highlights")}
      >
        <IcHighlight size={14} />
      </RailButton>
      <div style={{ flex: 1 }} />
      <RailButton label="Expand panel" onClick={() => onOpen("thread")}>
        <IcArrowL size={14} />
      </RailButton>
    </aside>
  );
}

function RailButton({
  children,
  label,
  pip,
  pipDark,
  onClick,
}: {
  children: React.ReactNode;
  label: string;
  pip?: boolean;
  pipDark?: boolean;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      title={label}
      aria-label={label}
      onClick={onClick}
      style={{
        width: 36,
        height: 36,
        borderRadius: 999,
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        cursor: "pointer",
        color: "var(--ink-2)",
        background: "none",
        border: 0,
        marginBottom: 4,
        transition: "all var(--dur)",
        position: "relative",
      }}
      onMouseOver={(e) => {
        (e.currentTarget.style.background = "var(--paper-1)"),
          (e.currentTarget.style.color = "var(--ink-0)");
      }}
      onMouseOut={(e) => {
        (e.currentTarget.style.background = "none"),
          (e.currentTarget.style.color = "var(--ink-2)");
      }}
    >
      {children}
      {pip && (
        <span
          aria-hidden="true"
          style={{
            position: "absolute",
            top: 6,
            right: 6,
            width: 6,
            height: 6,
            borderRadius: 999,
            background: pipDark ? "var(--ink-0)" : "var(--accent)",
          }}
        />
      )}
    </button>
  );
}
