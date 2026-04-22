import { useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import type { AskCard as AskCardT } from "../../lib/reader/cards";
import { SkeletonAskCard } from "./SkeletonAskCard";
import { BlinkingCursor } from "./BlinkingCursor";
import { FollowupComposer } from "./FollowupComposer";
import { JumpToAnchorCTA } from "./JumpToAnchorCTA";

export function AskCard({
  card,
  flash,
  enterDelay,
  offscreen,
  crossPage,
  onJump,
  onFollowup,
  composerRef,
}: {
  card: AskCardT;
  flash: boolean;
  enterDelay?: number;
  offscreen?: { direction: "up" | "down" };
  crossPage?: { direction: "left" | "right"; folio: number };
  onJump?: () => void;
  onFollowup?: (q: string) => void;
  composerRef?: React.Ref<HTMLInputElement>;
}) {
  const answerRef = useRef<HTMLDivElement | null>(null);
  // Gate: only play the enter animation on first mount (not on re-renders).
  const didMount = useRef(false);
  const enterClass = useMemo(() => {
    if (!didMount.current) {
      didMount.current = true;
      return "rr-card-enter";
    }
    return "";
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  const [isLong, setIsLong] = useState(false);

  // Local cursor visibility state — mirrors card.streaming but stays true for
  // 100ms after streaming ends so Playwright polling can detect it reliably.
  const [showCursor, setShowCursor] = useState(false);
  const cursorTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    if (card.streaming) {
      if (cursorTimer.current) {
        clearTimeout(cursorTimer.current);
        cursorTimer.current = null;
      }
      setShowCursor(true);
    } else {
      // Briefly keep cursor visible after streaming ends.
      cursorTimer.current = setTimeout(() => {
        setShowCursor(false);
        cursorTimer.current = null;
      }, 100);
    }
    return () => {
      if (cursorTimer.current) clearTimeout(cursorTimer.current);
    };
  }, [card.streaming]);

  useLayoutEffect(() => {
    const el = answerRef.current;
    if (!el) return;
    // Detect whether content exceeds the 220px cap.
    const tall = el.scrollHeight > 220;
    if (tall !== isLong) {
      setIsLong(tall);
    }
  });

  if (card.loading) {
    return <SkeletonAskCard />;
  }

  // Build header prefix text.
  let prefix = "";
  if (crossPage) {
    if (crossPage.direction === "left") {
      prefix = `← FROM p. ${crossPage.folio} · `;
    } else {
      prefix = `→ FROM p. ${crossPage.folio} · `;
    }
  } else if (offscreen) {
    if (offscreen.direction === "up") {
      prefix = "↑ SCROLL UP · ";
    } else {
      prefix = "↓ SCROLL DOWN · ";
    }
  }

  return (
    <article
      data-card-id={card.id}
      data-card-kind="ask"
      data-card-anchor={card.anchor}
      className={[
        "rr-card",
        enterClass,
        flash ? "rr-card-flash" : "",
      ].filter(Boolean).join(" ")}
      style={{
        background: "var(--paper-00)",
        border: "1px solid var(--paper-2)",
        borderLeft: "3px solid var(--accent)",
        borderRadius: 10,
        padding: "14px 16px",
        boxShadow: "0 4px 12px -4px rgba(28,24,18,.08)",
        transform: "rotate(-0.2deg)",
        fontFamily: "var(--serif)",
        ...(enterDelay != null ? { animationDelay: `${enterDelay}ms` } : {}),
      }}
    >
      <header
        style={{
          fontFamily: "var(--sans)",
          fontSize: 9.5,
          letterSpacing: 1.3,
          textTransform: "uppercase",
          color: "var(--accent-ink)",
          fontWeight: 600,
          marginBottom: 6,
        }}
      >
        {prefix}ASKED ABOUT "{card.quote}"
      </header>
      <div
        style={{
          fontStyle: "italic",
          fontSize: 13.5,
          color: "var(--ink-1)",
          marginBottom: 6,
        }}
      >
        {card.question}
      </div>
      <div style={{ position: "relative" }}>
        <div
          ref={answerRef}
          data-testid="ask-answer"
          style={{
            fontSize: 14,
            lineHeight: 1.62,
            color: "var(--ink-0)",
            maxHeight: 220,
            overflowY: "auto",
          }}
        >
          {card.answer}
          {showCursor && <BlinkingCursor />}
        </div>
        {isLong && (
          <div
            data-testid="ask-answer-fade"
            style={{
              position: "absolute",
              bottom: 0,
              left: 0,
              right: 0,
              height: 24,
              background:
                "linear-gradient(to bottom, transparent, var(--paper-00))",
              pointerEvents: "none",
            }}
          />
        )}
      </div>
      {/* S5: followup thread */}
      {card.followups.map((fu, i) => (
        <div
          key={i}
          data-testid="followup"
          style={{
            marginTop: 10,
            paddingLeft: 14,
            borderLeft: "1px dashed var(--paper-3)",
          }}
        >
          <div
            style={{
              fontFamily: "var(--sans)",
              fontSize: 9.5,
              letterSpacing: 1.3,
              textTransform: "uppercase",
              color: "var(--accent-ink)",
              fontWeight: 600,
              marginBottom: 4,
            }}
          >
            FOLLOW-UP
          </div>
          <div style={{ fontStyle: "italic", fontSize: 13, color: "var(--ink-1)", marginBottom: 4 }}>
            {fu.question}
          </div>
          <div style={{ fontSize: 14, lineHeight: 1.62, color: "var(--ink-0)" }}>
            {fu.answer}
            {card.followupLoading && i === card.followups.length - 1 && (
              <BlinkingCursor />
            )}
          </div>
        </div>
      ))}
      {/* Follow-up composer — hidden while loading */}
      {!card.loading && (
        <FollowupComposer
          ref={composerRef}
          onSubmit={onFollowup ?? (() => {})}
        />
      )}
      {/* S6: jump CTA */}
      {offscreen && onJump && <JumpToAnchorCTA onJump={onJump} />}
    </article>
  );
}
