import type { PropsWithChildren, ReactNode } from "react";

type ButtonProps = PropsWithChildren<{
  variant?: "primary" | "secondary" | "ghost";
  icon?: ReactNode;
  onClick?: () => void;
  title?: string;
}>;

const VARIANTS = {
  primary: { bg: "var(--ink-0)", color: "var(--paper-0)" },
  secondary: { bg: "var(--paper-1)", color: "var(--ink-0)" },
  ghost: { bg: "transparent", color: "var(--ink-1)" },
} as const;

export function Button({
  variant = "secondary",
  icon,
  children,
  onClick,
  title,
}: ButtonProps) {
  const v = VARIANTS[variant];
  return (
    <button
      type="button"
      onClick={onClick}
      title={title}
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: 8,
        padding: "7px 14px",
        height: 34,
        fontSize: 14,
        fontFamily: "var(--sans)",
        fontWeight: 500,
        borderRadius: "var(--r-md)",
        background: v.bg,
        color: v.color,
        border: 0,
        cursor: "pointer",
      }}
    >
      {icon}
      {children}
    </button>
  );
}
