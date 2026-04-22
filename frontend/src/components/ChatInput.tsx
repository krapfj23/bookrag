import { useState, type KeyboardEvent } from "react";
import { IcSend } from "./icons";

type ChatInputProps = {
  value: string;
  onChange: (next: string) => void;
  onSubmit: () => void;
  placeholder?: string;
  disabled?: boolean;
};

export function ChatInput({
  value,
  onChange,
  onSubmit,
  placeholder = "Ask about what you've read…",
  disabled = false,
}: ChatInputProps) {
  const [focus, setFocus] = useState(false);
  const canSend = !disabled && value.trim().length > 0;

  function handleKeyDown(e: KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      if (canSend) onSubmit();
    }
  }

  return (
    <div
      style={{
        display: "flex",
        alignItems: "flex-end",
        gap: 8,
        padding: "10px 10px 10px 16px",
        background: "var(--paper-00)",
        border: `1px solid ${focus ? "var(--accent)" : "var(--paper-2)"}`,
        boxShadow: focus
          ? "0 0 0 3px var(--accent-softer), var(--shadow-1)"
          : "var(--shadow-1)",
        borderRadius: "var(--r-lg)",
        transition:
          "border-color var(--dur) var(--ease), box-shadow var(--dur) var(--ease)",
        fontFamily: "var(--serif)",
      }}
    >
      <textarea
        value={value}
        onChange={(e) => onChange(e.target.value)}
        onFocus={() => setFocus(true)}
        onBlur={() => setFocus(false)}
        onKeyDown={handleKeyDown}
        placeholder={placeholder}
        disabled={disabled}
        rows={1}
        aria-label="Ask about what you've read"
        style={{
          flex: 1,
          border: 0,
          outline: "none",
          background: "transparent",
          resize: "none",
          fontFamily: "var(--serif)",
          fontSize: 15.5,
          lineHeight: 1.5,
          color: "var(--ink-0)",
          padding: "6px 0",
          minHeight: 24,
          maxHeight: 160,
        }}
      />
      <button
        type="button"
        onClick={onSubmit}
        disabled={!canSend}
        aria-label="Send"
        style={{
          width: 34,
          height: 34,
          borderRadius: "var(--r-md)",
          background: canSend ? "var(--accent)" : "var(--paper-1)",
          color: canSend ? "var(--paper-00)" : "var(--ink-3)",
          border: 0,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          cursor: canSend ? "pointer" : "not-allowed",
          transition: "background var(--dur) var(--ease), color var(--dur) var(--ease)",
        }}
      >
        <IcSend size={15} />
      </button>
    </div>
  );
}
