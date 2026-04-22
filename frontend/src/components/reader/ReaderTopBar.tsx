import { useNavigate } from "react-router-dom";
import { IcSearch, IcBookmark } from "../icons";
import { ReadingModeToggle } from "./ReadingModeToggle";
import type { ReadingMode } from "../../lib/reader/useReadingMode";

interface Props {
  title: string;
  spreadLabel?: string;
  mode: ReadingMode;
  onToggleMode: () => void;
  onAsk?: () => void;
  spreadIdx?: number;
  totalSpreads?: number;
}

export function ReaderTopBar({ title, mode, onToggleMode, onAsk, spreadIdx, totalSpreads }: Props) {
  const navigate = useNavigate();

  return (
    <header
      data-testid="reader-topbar"
      style={{
        display: "grid",
        gridTemplateColumns: "1fr auto 1fr",
        alignItems: "center",
        padding: "14px 28px",
        height: 52,
        borderBottom: "var(--hairline)",
        opacity: mode === "on" ? 0.55 : 1,
        transition: "opacity 240ms ease",
        background: "color-mix(in oklab, var(--paper-0) 80%, transparent)",
        backdropFilter: "saturate(140%) blur(12px)",
      }}
    >
      {/* Left: back to library */}
      <button
        type="button"
        onClick={() => navigate("/")}
        aria-label="Back to library"
        style={{
          fontFamily: "var(--sans)",
          fontSize: 13,
          color: "var(--ink-1)",
          justifySelf: "start",
          background: "transparent",
          border: 0,
          cursor: "pointer",
        }}
      >
        ← Library
      </button>

      {/* Center: chapter title */}
      <div
        style={{
          fontFamily: "var(--serif)",
          fontStyle: "italic",
          fontSize: 14,
          color: "var(--ink-0)",
        }}
      >
        {title}
      </div>

      {/* Right: spread counter, Search, Bookmark, Ask pill, Reading mode toggle */}
      <div
        style={{
          justifySelf: "end",
          display: "flex",
          alignItems: "center",
          gap: 8,
        }}
      >
        {spreadIdx != null && totalSpreads != null && (
          <div
            aria-hidden="true"
            style={{ color: "var(--ink-3)", fontSize: 12 }}
          >
            {`${spreadIdx + 1} / ${totalSpreads}`}
          </div>
        )}
        <button
          type="button"
          aria-label="Search"
          style={{
            background: "transparent",
            border: 0,
            cursor: "pointer",
            color: "var(--ink-2)",
            display: "flex",
            alignItems: "center",
            padding: "4px",
            borderRadius: 4,
          }}
        >
          <IcSearch size={16} />
        </button>
        <button
          type="button"
          aria-label="Bookmark"
          style={{
            background: "transparent",
            border: 0,
            cursor: "pointer",
            color: "var(--ink-2)",
            display: "flex",
            alignItems: "center",
            padding: "4px",
            borderRadius: 4,
          }}
        >
          <IcBookmark size={16} />
        </button>
        <button
          type="button"
          aria-label="Ask"
          data-testid="topbar-ask-pill"
          onClick={onAsk}
          style={{
            padding: "6px 14px",
            borderRadius: "999px",
            background: "var(--accent)",
            color: "var(--paper-00)",
            border: 0,
            fontFamily: "var(--sans)",
            fontSize: 12,
            fontWeight: 600,
            cursor: "pointer",
          }}
        >
          Ask
        </button>
        <ReadingModeToggle mode={mode} onToggle={onToggleMode} />
      </div>
    </header>
  );
}
