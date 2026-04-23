import { useEffect, useRef, useState } from "react";

export interface AskComposerPopoverProps {
  /** The highlighted text that will be pinned as context for the question. */
  quote: string;
  /** Viewport-absolute top (document coords, already + scrollY). */
  top: number;
  /** Viewport-absolute left (document coords, already + scrollX) — center. */
  left: number;
  onSubmit: (question: string) => void;
  onCancel: () => void;
}

export function AskComposerPopover({
  quote,
  top,
  left,
  onSubmit,
  onCancel,
}: AskComposerPopoverProps) {
  const [value, setValue] = useState("");
  const ref = useRef<HTMLTextAreaElement | null>(null);

  useEffect(() => {
    ref.current?.focus();
  }, []);

  function handleSubmit() {
    const trimmed = value.trim();
    if (trimmed.length === 0) return;
    onSubmit(trimmed);
  }

  const truncated =
    quote.length > 220 ? `${quote.slice(0, 220).trimEnd()}…` : quote;

  return (
    <div
      data-testid="ask-composer"
      role="dialog"
      aria-label="Ask a question about the selected text"
      style={{
        position: "absolute",
        top,
        left,
        transform: "translate(-50%, 8px)",
        zIndex: 200,
        width: 380,
        background: "var(--paper-00)",
        border: "var(--hairline)",
        borderRadius: "var(--r-md)",
        boxShadow:
          "0 18px 36px -14px rgba(28,24,18,.25), 0 6px 12px -6px rgba(28,24,18,.1)",
        padding: "14px 14px 12px",
        fontFamily: "var(--sans)",
      }}
      onKeyDown={(e) => {
        if (e.key === "Escape") {
          e.preventDefault();
          onCancel();
        }
      }}
    >
      <div
        style={{
          fontSize: 11,
          letterSpacing: 1.2,
          textTransform: "uppercase",
          color: "var(--ink-3)",
          marginBottom: 6,
        }}
      >
        About this passage
      </div>
      <blockquote
        style={{
          margin: "0 0 10px",
          padding: "8px 10px",
          borderLeft: "3px solid var(--accent)",
          background: "color-mix(in oklab, var(--accent) 6%, var(--paper-00))",
          fontFamily: "var(--serif)",
          fontStyle: "italic",
          fontSize: 13,
          lineHeight: 1.5,
          color: "var(--ink-1)",
          maxHeight: 100,
          overflow: "auto",
        }}
      >
        {truncated}
      </blockquote>
      <textarea
        ref={ref}
        data-testid="ask-composer-input"
        value={value}
        onChange={(e) => setValue(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === "Enter" && !e.shiftKey) {
            e.preventDefault();
            handleSubmit();
          }
        }}
        placeholder="Ask a question about this passage…"
        rows={3}
        style={{
          width: "100%",
          resize: "vertical",
          padding: "8px 10px",
          border: "1px solid var(--paper-2)",
          borderRadius: "var(--r-sm)",
          fontFamily: "var(--sans)",
          fontSize: 13,
          lineHeight: 1.45,
          color: "var(--ink-0)",
          background: "var(--paper-0)",
          boxSizing: "border-box",
          outline: "none",
        }}
      />
      <div
        style={{
          display: "flex",
          justifyContent: "flex-end",
          gap: 8,
          marginTop: 10,
        }}
      >
        <button
          type="button"
          data-testid="ask-composer-cancel"
          onClick={onCancel}
          style={{
            background: "transparent",
            border: "1px solid var(--paper-2)",
            borderRadius: "var(--r-sm)",
            padding: "6px 12px",
            fontSize: 12,
            color: "var(--ink-2)",
            cursor: "pointer",
          }}
        >
          Cancel
        </button>
        <button
          type="button"
          data-testid="ask-composer-submit"
          onClick={handleSubmit}
          disabled={value.trim().length === 0}
          style={{
            background: "var(--accent)",
            color: "var(--paper-00)",
            border: 0,
            borderRadius: "var(--r-sm)",
            padding: "6px 14px",
            fontSize: 12,
            fontWeight: 600,
            cursor: value.trim().length === 0 ? "not-allowed" : "pointer",
            opacity: value.trim().length === 0 ? 0.55 : 1,
          }}
        >
          Ask
        </button>
      </div>
    </div>
  );
}
