import type { CSSProperties } from "react";
import { moodForBookId, type Mood } from "../lib/mood";

type BookCoverProps = {
  book_id: string;
  title: string;
  mood?: Mood;
  style?: CSSProperties;
};

const PALETTE: Record<Mood, { bg: string; ink: string }> = {
  sage: { bg: "oklch(78% 0.04 145)", ink: "oklch(22% 0.03 145)" },
  amber: { bg: "oklch(82% 0.06 70)", ink: "oklch(26% 0.05 70)" },
  slate: { bg: "oklch(74% 0.03 240)", ink: "oklch(22% 0.03 240)" },
  rose: { bg: "oklch(80% 0.04 20)", ink: "oklch(24% 0.04 20)" },
  charcoal: { bg: "oklch(30% 0.01 50)", ink: "oklch(94% 0.01 70)" },
  paper: { bg: "oklch(92% 0.01 70)", ink: "oklch(22% 0.02 70)" },
};

export function BookCover({ book_id, title, mood, style }: BookCoverProps) {
  const chosen: Mood = mood ?? moodForBookId(book_id);
  const colors = PALETTE[chosen];
  return (
    <div
      data-mood={chosen}
      style={{
        position: "relative",
        background: colors.bg,
        color: colors.ink,
        aspectRatio: "2 / 3",
        borderRadius: "var(--r-xs)",
        padding: "18px 16px",
        display: "flex",
        flexDirection: "column",
        justifyContent: "space-between",
        boxShadow: "inset 0 0 0 1px rgba(0,0,0,0.06), 2px 2px 0 rgba(0,0,0,0.04)",
        overflow: "hidden",
        ...style,
      }}
    >
      <div
        style={{
          position: "absolute",
          inset: 8,
          border: "0.5px solid currentColor",
          opacity: 0.3,
          borderRadius: 1,
          pointerEvents: "none",
        }}
      />
      <div
        style={{
          fontFamily: "var(--sans)",
          fontSize: 9,
          letterSpacing: 1.5,
          textTransform: "uppercase",
          opacity: 0.65,
        }}
      >
        a novel
      </div>
      <div>
        <div
          style={{
            fontFamily: "var(--serif)",
            fontWeight: 500,
            fontStyle: "italic",
            fontSize: 19,
            lineHeight: 1.15,
            letterSpacing: -0.3,
          }}
        >
          {title}
        </div>
      </div>
    </div>
  );
}
