import { useEffect, useRef, useState } from "react";
import { IcClose, IcPrivate } from "./icons";

interface Props {
  excerpt: string;
  onCancel: () => void;
  onSave: (body: string, tags: string[]) => void;
}

// Modal composer for a new note. Backdrop click OR Esc cancels. Cmd/Ctrl+Enter
// saves. Empty body is blocked by disabling the Save button.
export function NoteComposer({ excerpt, onCancel, onSave }: Props) {
  const [body, setBody] = useState("");
  const [tagDraft, setTagDraft] = useState("");
  const [tags, setTags] = useState<string[]>([]);
  const bodyRef = useRef<HTMLTextAreaElement | null>(null);

  useEffect(() => {
    bodyRef.current?.focus();
  }, []);

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") {
        e.stopPropagation();
        onCancel();
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onCancel]);

  function addTag() {
    const t = tagDraft.trim().replace(/^#?/, "#");
    if (t.length < 2) return;
    if (!tags.includes(t)) setTags((prev) => [...prev, t]);
    setTagDraft("");
  }

  const canSave = body.trim().length > 0;

  return (
    <div
      role="dialog"
      aria-label="Write a note"
      aria-modal="true"
      style={{
        position: "fixed",
        inset: 0,
        background: "rgba(32,28,22,0.28)",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        zIndex: 40,
        animation: "annot-fadeUp 160ms var(--ease-out)",
      }}
      onClick={onCancel}
    >
      <div
        onClick={(e) => e.stopPropagation()}
        style={{
          width: 520,
          background: "var(--paper-00)",
          border: "1px solid var(--paper-2)",
          borderRadius: "var(--r-lg)",
          boxShadow: "0 24px 52px rgba(32,28,22,0.22)",
          padding: 20,
          fontFamily: "var(--sans)",
        }}
      >
        <header
          style={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            marginBottom: 14,
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
            Write a note
          </div>
          <span className="annot-private-chip">
            <IcPrivate size={8} /> private
          </span>
        </header>

        <div
          style={{
            fontSize: 9,
            letterSpacing: 0.8,
            textTransform: "uppercase",
            color: "var(--ink-3)",
            marginBottom: 4,
          }}
        >
          highlighted passage
        </div>
        <div
          style={{
            background: "color-mix(in oklab, var(--accent-soft) 85%, transparent)",
            padding: "8px 12px",
            borderRadius: 4,
            fontFamily: "var(--serif)",
            fontStyle: "italic",
            fontSize: 13.5,
            color: "var(--ink-1)",
            lineHeight: 1.5,
            marginBottom: 16,
            maxHeight: 96,
            overflow: "auto",
          }}
        >
          {excerpt}
        </div>

        <textarea
          ref={bodyRef}
          value={body}
          onChange={(e) => setBody(e.target.value)}
          onKeyDown={(e) => {
            if ((e.metaKey || e.ctrlKey) && e.key === "Enter" && canSave) {
              e.preventDefault();
              onSave(body.trim(), tags);
            }
          }}
          placeholder="What struck you about this passage?"
          aria-label="Note body"
          style={{
            width: "100%",
            minHeight: 110,
            padding: 12,
            fontFamily: "var(--serif)",
            fontSize: 14.5,
            lineHeight: 1.6,
            color: "var(--ink-0)",
            background: "var(--paper-0)",
            border: "1px solid var(--paper-2)",
            borderRadius: "var(--r-md)",
            resize: "vertical",
            boxSizing: "border-box",
          }}
        />

        <div style={{ display: "flex", gap: 6, marginTop: 10, flexWrap: "wrap" }}>
          {tags.map((t) => (
            <span
              key={t}
              className="annot-tag"
              onClick={() => setTags((prev) => prev.filter((x) => x !== t))}
              title="Remove tag"
            >
              {t} ×
            </span>
          ))}
          <input
            value={tagDraft}
            onChange={(e) => setTagDraft(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" || e.key === ",") {
                e.preventDefault();
                addTag();
              }
            }}
            placeholder="#add-tag"
            aria-label="Add tag"
            style={{
              padding: "3px 6px",
              fontFamily: "var(--mono)",
              fontSize: 10,
              border: "1px dashed var(--paper-2)",
              background: "transparent",
              color: "var(--ink-2)",
              borderRadius: 3,
              width: 90,
            }}
          />
        </div>

        <footer
          style={{
            display: "flex",
            justifyContent: "flex-end",
            gap: 8,
            marginTop: 18,
          }}
        >
          <button
            type="button"
            onClick={onCancel}
            aria-label="Cancel note"
            style={{
              background: "transparent",
              border: 0,
              padding: "8px 14px",
              color: "var(--ink-2)",
              fontFamily: "var(--sans)",
              fontSize: 13,
              fontWeight: 500,
              borderRadius: "var(--r-md)",
              cursor: "pointer",
            }}
          >
            <IcClose size={11} /> Cancel
          </button>
          <button
            type="button"
            disabled={!canSave}
            onClick={() => onSave(body.trim(), tags)}
            style={{
              background: canSave ? "var(--accent)" : "var(--paper-1)",
              border: 0,
              padding: "8px 16px",
              color: canSave ? "var(--paper-00)" : "var(--ink-3)",
              fontFamily: "var(--sans)",
              fontSize: 13,
              fontWeight: 500,
              borderRadius: "var(--r-md)",
              cursor: canSave ? "pointer" : "not-allowed",
            }}
          >
            Save note
          </button>
        </footer>
      </div>
    </div>
  );
}
