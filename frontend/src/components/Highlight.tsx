import type { PropsWithChildren, CSSProperties } from "react";

export type HighlightVariant = "mark" | "selection" | "entity" | "quote";

type HighlightProps = PropsWithChildren<{
  variant?: HighlightVariant;
}>;

const STYLES: Record<HighlightVariant, CSSProperties> = {
  mark: {
    background: "color-mix(in oklab, var(--accent-soft) 70%, transparent)",
    color: "var(--ink-0)",
  },
  selection: { background: "var(--accent)", color: "var(--paper-00)" },
  entity: { borderBottom: "1.5px solid var(--accent)", color: "var(--ink-0)" },
  quote: { background: "var(--accent-softer)", color: "var(--ink-0)" },
};

export function Highlight({ variant = "mark", children }: HighlightProps) {
  return (
    <span
      data-variant={variant}
      style={{ padding: "0 2px", borderRadius: "var(--r-xs)", ...STYLES[variant] }}
    >
      {children}
    </span>
  );
}
