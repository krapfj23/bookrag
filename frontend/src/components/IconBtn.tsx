import type { PropsWithChildren } from "react";

type IconBtnProps = PropsWithChildren<{
  onClick?: () => void;
  title?: string;
  active?: boolean;
}>;

export function IconBtn({ children, onClick, title, active }: IconBtnProps) {
  return (
    <button
      onClick={onClick}
      title={title}
      type="button"
      style={{
        width: 30,
        height: 30,
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        borderRadius: "var(--r-sm)",
        color: active ? "var(--ink-0)" : "var(--ink-2)",
        background: active ? "var(--paper-1)" : "transparent",
        border: 0,
        cursor: "pointer",
        transition: "background var(--dur) var(--ease), color var(--dur) var(--ease)",
      }}
    >
      {children}
    </button>
  );
}
