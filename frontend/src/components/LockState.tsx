import { IcLock, IcBookmark, IcUnlock } from "./icons";

type CommonLabel = { label: string };
type LockStateProps =
  | ({ variant: "spoilerSafe" } & CommonLabel)
  | ({ variant: "locked" } & Partial<CommonLabel>)
  | ({ variant: "unlocked" } & Partial<CommonLabel>)
  | ({ variant: "current" } & Partial<CommonLabel>)
  | {
      variant: "chapterLock";
      chapterNum: number;
      chapterTitle: string;
    };

export function LockState(props: LockStateProps) {
  if (props.variant === "chapterLock") {
    return (
      <div
        style={{
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          justifyContent: "center",
          padding: "80px 40px",
          gap: 16,
          color: "var(--ink-3)",
          fontFamily: "var(--sans)",
        }}
      >
        <div
          style={{
            width: 44,
            height: 44,
            borderRadius: 999,
            background: "var(--paper-1)",
            color: "var(--ink-2)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
          }}
        >
          <IcLock size={18} />
        </div>
        <div
          style={{
            fontFamily: "var(--serif)",
            fontSize: 22,
            color: "var(--ink-0)",
            letterSpacing: -0.3,
            textAlign: "center",
          }}
        >
          {props.chapterTitle}
        </div>
        <div style={{ fontSize: 13, color: "var(--ink-3)" }}>
          Locked — reach chapter {props.chapterNum} to unlock
        </div>
      </div>
    );
  }

  const { variant } = props;
  const label =
    "label" in props && props.label
      ? props.label
      : variant === "locked"
      ? "Locked"
      : variant === "unlocked"
      ? "Unlocked"
      : variant === "current"
      ? "You're here"
      : "Spoiler-safe";
  const Icon =
    variant === "spoilerSafe" || variant === "locked"
      ? IcLock
      : variant === "current"
      ? IcBookmark
      : IcUnlock;
  const color =
    variant === "locked" ? "var(--ink-3)" : "var(--accent)";

  return (
    <span
      role="status"
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: 6,
        fontFamily: "var(--sans)",
        fontSize: 12,
        color,
        letterSpacing: 0.2,
      }}
    >
      <Icon size={12} />
      {label}
    </span>
  );
}
