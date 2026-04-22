import { useState } from "react";

export function FollowupComposer({
  onSubmit,
}: {
  onSubmit: (question: string) => void;
}) {
  const [value, setValue] = useState("");

  function handleKeyDown(e: React.KeyboardEvent<HTMLInputElement>) {
    if (e.key === "Enter") {
      const trimmed = value.trim();
      if (!trimmed) return;
      onSubmit(trimmed);
      setValue("");
    }
  }

  return (
    <input
      type="text"
      placeholder="Ask a follow-up…"
      value={value}
      onChange={(e) => setValue(e.target.value)}
      onKeyDown={handleKeyDown}
      style={{
        marginTop: 10,
        width: "100%",
        border: "1px dashed var(--paper-3)",
        borderRadius: 6,
        padding: "6px 10px",
        fontFamily: "var(--serif)",
        fontSize: 13.5,
        color: "var(--ink-0)",
        background: "transparent",
        outline: "none",
        boxSizing: "border-box",
      }}
    />
  );
}
