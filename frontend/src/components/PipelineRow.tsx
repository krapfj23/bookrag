import type { CSSProperties } from "react";
import { StatusBadge, type BadgeState } from "./StatusBadge";
import { IcCheck, IcClose } from "./icons";

type PipelineRowProps = {
  title: string;
  description: string;
  state: BadgeState;
  meta?: string;
};

export function PipelineRow({ title, description, state, meta }: PipelineRowProps) {
  const indicatorColor =
    state === "done"
      ? "var(--ok)"
      : state === "running"
        ? "var(--accent)"
        : state === "error"
          ? "var(--err)"
          : "var(--ink-4)";

  const indicatorBg =
    state === "done"
      ? "color-mix(in oklab, var(--ok) 18%, var(--paper-0))"
      : state === "running"
        ? "var(--accent-softer)"
        : "transparent";

  const rootStyle: CSSProperties = {
    display: "grid",
    gridTemplateColumns: "24px 1fr auto auto",
    alignItems: "center",
    gap: 16,
    padding: "14px 4px",
    borderBottom: "var(--hairline)",
    fontFamily: "var(--sans)",
    opacity: state === "idle" ? 0.55 : 1,
    transition: "opacity var(--dur) var(--ease)",
  };

  return (
    <div style={rootStyle}>
      <div
        style={{
          width: 20,
          height: 20,
          borderRadius: 999,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          color: indicatorColor,
          background: indicatorBg,
          border: state === "idle" ? "1px solid var(--paper-3)" : "none",
        }}
      >
        {state === "done" ? (
          <IcCheck size={12} />
        ) : state === "error" ? (
          <IcClose size={11} />
        ) : state === "running" ? (
          <span
            style={{
              width: 6,
              height: 6,
              borderRadius: 999,
              background: "currentColor",
              animation: "brPulse 1.6s var(--ease-out) infinite",
            }}
          />
        ) : null}
      </div>

      <div>
        <div
          style={{
            fontSize: 14,
            fontWeight: 500,
            color: "var(--ink-0)",
            fontFamily: "var(--sans)",
            letterSpacing: 0.1,
          }}
        >
          {title}
        </div>
        <div style={{ fontSize: 12, color: "var(--ink-2)", marginTop: 2 }}>
          {description}
        </div>
      </div>

      {meta ? (
        <div
          data-pipeline-meta
          style={{
            fontSize: 11,
            color: state === "error" ? "var(--err)" : "var(--ink-3)",
            fontVariantNumeric: "tabular-nums",
            maxWidth: 260,
            textAlign: "right",
          }}
        >
          {meta}
        </div>
      ) : (
        <span />
      )}

      <StatusBadge state={state} />
    </div>
  );
}
