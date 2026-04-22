import { useEffect, useRef } from "react";
import type { NoteCard as NoteCardT } from "../../lib/reader/cards";

export function NoteCard({
  card,
  flash,
  autoFocus,
  onBodyChange,
  onBodyCommit,
}: {
  card: NoteCardT;
  flash: boolean;
  autoFocus: boolean;
  onBodyChange: (id: string, next: string) => void;
  onBodyCommit: (id: string) => void;
}) {
  const ref = useRef<HTMLTextAreaElement | null>(null);
  useEffect(() => {
    if (autoFocus && ref.current) ref.current.focus();
  }, [autoFocus]);

  return (
    <article
      data-card-id={card.id}
      data-card-kind="note"
      data-card-anchor={card.anchor}
      className={flash ? "rr-card rr-card-flash" : "rr-card"}
      style={{
        background: "var(--paper-00)",
        border: "1px solid var(--paper-2)",
        borderLeft: "3px solid oklch(58% 0.1 55)",
        borderRadius: 10,
        padding: "14px 16px",
        boxShadow: "0 4px 12px -4px rgba(28,24,18,.08)",
        transform: "rotate(0.2deg)",
        fontFamily: "var(--serif)",
      }}
    >
      <header
        style={{
          fontFamily: "var(--sans)",
          fontSize: 9.5,
          letterSpacing: 1.3,
          textTransform: "uppercase",
          color: "oklch(30% 0.1 55)",
          fontWeight: 600,
          marginBottom: 6,
        }}
      >
        NOTED "{card.quote}"
      </header>
      <textarea
        ref={ref}
        aria-label="Note body"
        data-testid="note-body"
        value={card.body}
        onChange={(e) => onBodyChange(card.id, e.target.value)}
        onBlur={() => onBodyCommit(card.id)}
        onKeyDown={(e) => {
          if (e.key === "Enter" && !e.shiftKey) {
            e.preventDefault();
            onBodyCommit(card.id);
          }
        }}
        placeholder="Type your note…"
        rows={3}
        style={{
          width: "100%",
          resize: "vertical",
          border: 0,
          background: "transparent",
          fontFamily: "var(--serif)",
          fontSize: 14,
          lineHeight: 1.62,
          color: "var(--ink-0)",
          outline: "none",
          padding: 0,
        }}
      />
    </article>
  );
}
