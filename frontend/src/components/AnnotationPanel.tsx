import type { Annotation } from "../lib/annotations";
import { LockState } from "./LockState";
import { IcBookmark, IcClose, IcEdit, IcHighlight, IcPrivate, IcSpark } from "./icons";

export type PanelTab = "thread" | "notes" | "highlights";

interface Props {
  tab: PanelTab;
  onTabChange: (t: PanelTab) => void;
  onClose: () => void;
  // Content for each tab
  thread: React.ReactNode;
  notes: Annotation[];
  highlights: Annotation[];
  spoilerSafeLabel: string;
  // Which annotation (if any) was just activated from inline click → panel.
  focusedAnnotationId?: string;
  threadCount?: number;
}

// 400-pixel expanded panel. Slides in from the right when the user clicks a
// rail button or a peek's "Open in panel" action.
export function AnnotationPanel({
  tab,
  onTabChange,
  onClose,
  thread,
  notes,
  highlights,
  spoilerSafeLabel,
  focusedAnnotationId,
  threadCount,
}: Props) {
  return (
    <aside
      aria-label="Annotations panel"
      style={{
        width: 400,
        borderLeft: "var(--hairline)",
        background: "color-mix(in oklab, var(--paper-0) 92%, var(--paper-1))",
        display: "flex",
        flexDirection: "column",
        // Pin to the viewport so the chat input is always reachable,
        // instead of stretching to the full document height.
        position: "sticky",
        top: 56, // below NavBar
        height: "calc(100vh - 56px)",
        alignSelf: "start",
        overflow: "hidden",
      }}
    >
      {/* Spoiler-safe header band — preserves the invariant from slice 3 */}
      <div
        style={{
          padding: "10px 16px",
          borderBottom: "var(--hairline)",
          display: "flex",
          justifyContent: "flex-end",
          alignItems: "center",
        }}
      >
        <LockState variant="spoilerSafe" label={spoilerSafeLabel} />
      </div>

      {/* Tab strip */}
      <div
        style={{
          display: "flex",
          borderBottom: "var(--hairline)",
          padding: "0 16px",
          gap: 2,
        }}
      >
        <PanelTabButton
          active={tab === "thread"}
          onClick={() => onTabChange("thread")}
          label="Thread"
          count={threadCount}
        >
          <IcSpark size={12} />
        </PanelTabButton>
        <PanelTabButton
          active={tab === "notes"}
          onClick={() => onTabChange("notes")}
          label="Notes"
          count={notes.length}
        >
          <IcEdit size={12} />
        </PanelTabButton>
        <PanelTabButton
          active={tab === "highlights"}
          onClick={() => onTabChange("highlights")}
          label="Highlights"
          count={highlights.length}
        >
          <IcHighlight size={12} />
        </PanelTabButton>
        <div style={{ flex: 1 }} />
        <button
          type="button"
          onClick={onClose}
          aria-label="Close panel"
          style={{
            padding: "14px 10px",
            background: "none",
            border: 0,
            color: "var(--ink-3)",
            cursor: "pointer",
          }}
        >
          <IcClose size={13} />
        </button>
      </div>

      {/* Tab body */}
      {tab === "thread" && (
        <div
          style={{
            flex: 1,
            display: "flex",
            flexDirection: "column",
            minHeight: 0,
          }}
        >
          {thread}
        </div>
      )}
      {tab === "notes" && (
        <NotesTabBody notes={notes} focusedAnnotationId={focusedAnnotationId} />
      )}
      {tab === "highlights" && (
        <HighlightsTabBody
          highlights={highlights}
          focusedAnnotationId={focusedAnnotationId}
        />
      )}
    </aside>
  );
}

function PanelTabButton({
  active,
  onClick,
  label,
  count,
  children,
}: {
  active: boolean;
  onClick: () => void;
  label: string;
  count?: number;
  children: React.ReactNode;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-selected={active}
      data-tab={label.toLowerCase()}
      style={{
        background: "none",
        border: 0,
        padding: "14px 14px 12px",
        fontFamily: "var(--sans)",
        fontSize: 12.5,
        fontWeight: 500,
        color: active ? "var(--ink-0)" : "var(--ink-3)",
        cursor: "pointer",
        borderBottom: `2px solid ${active ? "var(--ink-0)" : "transparent"}`,
        display: "inline-flex",
        alignItems: "center",
        gap: 6,
      }}
    >
      {children}
      {label}
      {typeof count === "number" && (
        <span
          style={{
            background: active ? "var(--ink-0)" : "var(--paper-2)",
            color: active ? "var(--paper-00)" : "var(--ink-2)",
            fontSize: 10.5,
            padding: "1px 6px",
            borderRadius: 999,
            fontWeight: 500,
          }}
        >
          {count}
        </span>
      )}
    </button>
  );
}

function NotesTabBody({
  notes,
  focusedAnnotationId,
}: {
  notes: Annotation[];
  focusedAnnotationId?: string;
}) {
  return (
    <>
      <div style={{ flex: 1, overflow: "auto", padding: "16px 18px" }}>
        {notes.length === 0 && (
          <div
            role="status"
            style={{
              fontFamily: "var(--serif)",
              fontStyle: "italic",
              color: "var(--ink-3)",
              fontSize: 14,
              padding: "24px 4px",
            }}
          >
            No notes in this book yet. Highlight a passage to capture one.
          </div>
        )}
        {[...notes]
          // Focused note floats to the top
          .sort((a, b) => {
            if (a.id === focusedAnnotationId) return -1;
            if (b.id === focusedAnnotationId) return 1;
            return 0;
          })
          .map((n) => (
            <NoteCard key={n.id} note={n} focused={n.id === focusedAnnotationId} />
          ))}
      </div>
      <NoteComposerStub />
    </>
  );
}

function NoteCard({ note, focused }: { note: Annotation; focused: boolean }) {
  return (
    <div
      data-note-id={note.id}
      data-focused={focused ? "true" : "false"}
      style={{
        background: "var(--paper-00)",
        border: "1px solid var(--paper-2)",
        borderRadius: "var(--r-lg)",
        padding: 14,
        marginBottom: 12,
        boxShadow: focused ? "0 0 0 1px var(--accent)" : undefined,
      }}
    >
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          marginBottom: 10,
        }}
      >
        <div
          style={{
            fontSize: 10.5,
            letterSpacing: 1.4,
            textTransform: "uppercase",
            color: "var(--ink-3)",
          }}
        >
          Your note · {note.created_at} · Ch. {note.chapter}
        </div>
        <span className="annot-private-chip">
          <IcPrivate size={8} /> private
        </span>
      </div>
      <div
        style={{
          fontSize: 9,
          color: "var(--ink-3)",
          letterSpacing: 0.8,
          textTransform: "uppercase",
          fontFamily: "var(--sans)",
          marginBottom: 4,
        }}
      >
        highlighted passage
      </div>
      <div
        style={{
          background: "color-mix(in oklab, var(--accent-soft) 85%, transparent)",
          padding: "6px 10px",
          borderRadius: 4,
          fontFamily: "var(--serif)",
          fontStyle: "italic",
          fontSize: 12.5,
          color: "var(--ink-1)",
          lineHeight: 1.45,
          marginBottom: 14,
        }}
      >
        {note.match}
      </div>
      <div
        style={{
          fontFamily: "var(--serif)",
          fontSize: 14.5,
          color: "var(--ink-0)",
          lineHeight: 1.6,
        }}
      >
        {note.body}
      </div>
      {note.tags && note.tags.length > 0 && (
        <div style={{ marginTop: 12, display: "flex", gap: 5 }}>
          {note.tags.map((t) => (
            <span key={t} className="annot-tag">
              {t}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}

function NoteComposerStub() {
  return (
    <div
      style={{
        borderTop: "var(--hairline)",
        padding: "12px 16px",
        background: "var(--paper-00)",
        display: "flex",
        gap: 8,
        alignItems: "center",
      }}
    >
      <IcEdit size={13} style={{ color: "var(--ink-3)" }} />
      <span
        style={{
          flex: 1,
          fontFamily: "var(--serif)",
          fontStyle: "italic",
          fontSize: 13,
          color: "var(--ink-3)",
        }}
      >
        Write a new note…
      </span>
      <span className="annot-private-chip">
        <IcPrivate size={8} /> private
      </span>
    </div>
  );
}

function HighlightsTabBody({
  highlights,
  focusedAnnotationId,
}: {
  highlights: Annotation[];
  focusedAnnotationId?: string;
}) {
  if (highlights.length === 0) {
    return (
      <div
        role="status"
        style={{
          flex: 1,
          padding: "40px 24px",
          fontFamily: "var(--serif)",
          fontStyle: "italic",
          color: "var(--ink-3)",
          fontSize: 14,
        }}
      >
        Questions you've asked about passages appear here.
      </div>
    );
  }
  return (
    <div style={{ flex: 1, overflow: "auto", padding: "16px 18px" }}>
      {highlights.map((q) => (
        <div
          key={q.id}
          data-highlight-id={q.id}
          style={{
            background: "var(--paper-00)",
            border: "1px solid var(--paper-2)",
            borderRadius: "var(--r-lg)",
            padding: 14,
            marginBottom: 12,
            boxShadow:
              q.id === focusedAnnotationId ? "0 0 0 1px var(--accent)" : undefined,
          }}
        >
          <div
            style={{
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
              marginBottom: 10,
            }}
          >
            <div
              style={{
                fontSize: 10.5,
                letterSpacing: 1.4,
                textTransform: "uppercase",
                color: "var(--ink-3)",
              }}
            >
              Question · Ch. {q.chapter}
            </div>
            {q.bookmarked && (
              <IcBookmark size={11} style={{ color: "var(--accent)" }} />
            )}
          </div>
          <div
            style={{
              fontFamily: "var(--serif)",
              fontSize: 14.5,
              color: "var(--ink-0)",
              lineHeight: 1.4,
              fontWeight: 500,
              marginBottom: 6,
            }}
          >
            {q.question}
          </div>
          <div
            style={{
              fontFamily: "var(--serif)",
              fontSize: 13,
              fontStyle: "italic",
              color: "var(--ink-2)",
              lineHeight: 1.55,
            }}
          >
            {q.answer_excerpt}
          </div>
        </div>
      ))}
    </div>
  );
}
