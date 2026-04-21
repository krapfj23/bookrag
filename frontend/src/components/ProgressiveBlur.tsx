import type { PropsWithChildren } from "react";
import { IcLock } from "./icons";

type ProgressiveBlurProps = PropsWithChildren<{
  locked: boolean;
  height?: number;
}>;

export function ProgressiveBlur({
  locked,
  height = 260,
  children,
}: ProgressiveBlurProps) {
  return (
    <div style={{ position: "relative", overflow: "hidden" }}>
      {children}
      {locked && (
        <>
          <div
            aria-hidden="true"
            style={{
              position: "absolute",
              left: 0,
              right: 0,
              bottom: 0,
              height,
              pointerEvents: "none",
              background: `linear-gradient(to bottom,
                transparent 0%,
                color-mix(in oklab, var(--paper-0) 25%, transparent) 27.5%,
                color-mix(in oklab, var(--paper-0) 65%, transparent) 58.5%,
                var(--paper-0) 100%)`,
              backdropFilter: "blur(6px)",
              maskImage:
                "linear-gradient(to bottom, transparent 0%, #000 33%, #000 100%)",
              WebkitMaskImage:
                "linear-gradient(to bottom, transparent 0%, #000 33%, #000 100%)",
            }}
          />
          <div
            style={{
              position: "absolute",
              bottom: 40,
              left: 0,
              right: 0,
              display: "flex",
              justifyContent: "center",
              pointerEvents: "none",
            }}
          >
            <div
              style={{
                display: "inline-flex",
                alignItems: "center",
                gap: 8,
                padding: "8px 14px",
                borderRadius: "var(--r-pill)",
                background: "var(--paper-00)",
                color: "var(--ink-1)",
                boxShadow: "var(--shadow-1)",
                border: "var(--hairline)",
                fontFamily: "var(--sans)",
                fontSize: 12,
                pointerEvents: "auto",
                letterSpacing: 0.2,
              }}
            >
              <IcLock size={12} /> beyond your page — advance to reveal
            </div>
          </div>
        </>
      )}
    </div>
  );
}
