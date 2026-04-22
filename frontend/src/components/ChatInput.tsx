import type { KeyboardEvent } from "react";
import { IcSend } from "./icons";
import "./ChatInput.css";

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
  const canSend = !disabled && value.trim().length > 0;

  function handleKeyDown(e: KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      if (canSend) onSubmit();
    }
  }

  return (
    <div className="chat-input">
      <textarea
        value={value}
        onChange={(e) => onChange(e.target.value)}
        onKeyDown={handleKeyDown}
        placeholder={placeholder}
        disabled={disabled}
        rows={1}
        aria-label="Ask about what you've read"
        className="chat-input-textarea"
      />
      <button
        type="button"
        onClick={onSubmit}
        disabled={!canSend}
        aria-label="Send"
        className={`chat-input-send${canSend ? " can-send" : ""}`}
      >
        <IcSend size={15} />
      </button>
    </div>
  );
}
