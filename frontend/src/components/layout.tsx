import type { CSSProperties, PropsWithChildren } from "react";

type StackProps = PropsWithChildren<{ gap?: number; style?: CSSProperties }>;
export function Stack({ gap = 16, children, style }: StackProps) {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap, ...style }}>
      {children}
    </div>
  );
}

type RowProps = PropsWithChildren<{
  gap?: number;
  align?: CSSProperties["alignItems"];
  style?: CSSProperties;
}>;
export function Row({ gap = 12, align = "center", children, style }: RowProps) {
  return (
    <div style={{ display: "flex", alignItems: align, gap, ...style }}>
      {children}
    </div>
  );
}

export function Divider({ style }: { style?: CSSProperties }) {
  return (
    <div
      style={{
        height: 1,
        background: "var(--paper-2)",
        width: "100%",
        ...style,
      }}
    />
  );
}
