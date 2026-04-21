import type { ReactNode } from "react";
import { useState } from "react";

type TextInputProps = {
  placeholder?: string;
  value?: string;
  onChange?: (v: string) => void;
  icon?: ReactNode;
  size?: "sm" | "md" | "lg";
};

const HEIGHTS = { sm: 30, md: 38, lg: 44 } as const;

export function TextInput({
  placeholder,
  value,
  onChange,
  icon,
  size = "md",
}: TextInputProps) {
  const [focus, setFocus] = useState(false);
  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        gap: 8,
        height: HEIGHTS[size],
        padding: "0 12px",
        background: "var(--paper-00)",
        color: "var(--ink-0)",
        border: `1px solid ${focus ? "var(--accent)" : "var(--paper-2)"}`,
        boxShadow: focus ? "0 0 0 3px var(--accent-softer)" : "none",
        borderRadius: "var(--r-md)",
        transition:
          "border-color var(--dur) var(--ease), box-shadow var(--dur) var(--ease)",
        fontFamily: "var(--sans)",
      }}
    >
      {icon && <span style={{ color: "var(--ink-3)" }}>{icon}</span>}
      <input
        value={value ?? ""}
        onChange={(e) => onChange?.(e.target.value)}
        onFocus={() => setFocus(true)}
        onBlur={() => setFocus(false)}
        placeholder={placeholder}
        style={{
          flex: 1,
          border: 0,
          outline: "none",
          background: "transparent",
          fontFamily: "var(--sans)",
          fontSize: 14,
          color: "var(--ink-0)",
        }}
      />
    </div>
  );
}
