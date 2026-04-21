import type { CSSProperties } from "react";

export type BadgeState = "idle" | "queued" | "running" | "done" | "error";

type StatusBadgeProps = {
  state: BadgeState;
  label?: string;
};

type Variant = {
  bg: string;
  fg: string;
  dot: string;
  pulse?: boolean;
};

const VARIANTS: Record<BadgeState, Variant> = {
  idle:    { bg: "var(--paper-1)",     fg: "var(--ink-2)",      dot: "var(--ink-3)" },
  queued:  { bg: "var(--paper-1)",     fg: "var(--ink-1)",      dot: "var(--ink-3)" },
  running: { bg: "var(--accent-softer)", fg: "var(--accent-ink)", dot: "var(--accent)", pulse: true },
  done:    { bg: "var(--accent-softer)", fg: "var(--accent-ink)", dot: "var(--ok)" },
  error:   {
    bg: "color-mix(in oklab, var(--err) 12%, var(--paper-0))",
    fg: "var(--err)",
    dot: "var(--err)",
  },
};

const DEFAULT_LABELS: Record<BadgeState, string> = {
  idle: "idle",
  queued: "queued",
  running: "running",
  done: "done",
  error: "failed",
};

export function StatusBadge({ state, label }: StatusBadgeProps) {
  const v = VARIANTS[state];
  const ariaLabel = DEFAULT_LABELS[state];
  const text = label ?? DEFAULT_LABELS[state];

  const rootStyle: CSSProperties = {
    display: "inline-flex",
    alignItems: "center",
    gap: 7,
    height: 22,
    padding: "0 10px",
    borderRadius: "var(--r-pill)",
    background: v.bg,
    color: v.fg,
    fontFamily: "var(--sans)",
    fontSize: 11,
    fontWeight: 500,
    letterSpacing: 0.4,
    textTransform: "uppercase",
  };

  const dotStyle: CSSProperties = {
    width: 6,
    height: 6,
    borderRadius: 999,
    background: v.dot,
    boxShadow: v.pulse ? "0 0 0 0 currentColor" : "none",
    animation: v.pulse ? "brPulse 1.6s var(--ease-out) infinite" : "none",
  };

  return (
    <span role="status" aria-label={ariaLabel} style={rootStyle}>
      <span data-pulse={v.pulse ? "true" : "false"} style={dotStyle} />
      {text}
    </span>
  );
}
