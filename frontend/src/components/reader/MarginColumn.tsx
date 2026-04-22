import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { Card } from "../../lib/reader/cards";
import { AskCard } from "./AskCard";
import { NoteCard } from "./NoteCard";
import { S1EmptyCard } from "./S1EmptyCard";
import { CollapsedCardRow } from "./CollapsedCardRow";
import { LatestExpandedDivider } from "./LatestExpandedDivider";
import { AnchorConnector } from "./AnchorConnector";
import { AnchorEdgeBar } from "./AnchorEdgeBar";
import { useAnchorVisibility } from "../../lib/reader/useAnchorVisibility";
import { computeCrossPage } from "../../lib/reader/pageSide";
import { getAnchorRect } from "../../lib/reader/anchorGeometry";

function partitionWithOverrides(
  cards: Card[],
  manuallyExpandedIds: Set<string>,
): { collapsed: Card[]; expanded: Card[] } {
  if (cards.length <= 2) {
    return { collapsed: [], expanded: [...cards] };
  }
  // Sort by updatedAt descending; top 2 are "naturally expanded".
  const sorted = [...cards].sort(
    (a, b) =>
      new Date(b.updatedAt).getTime() - new Date(a.updatedAt).getTime(),
  );
  const naturalExpandedIds = new Set([sorted[0].id, sorted[1].id]);

  // Merge manual overrides: add manually expanded, remove the oldest-natural
  // that was displaced to make room. We keep exactly 2 expanded.
  const expandedIds = new Set(naturalExpandedIds);
  for (const id of manuallyExpandedIds) {
    if (!expandedIds.has(id)) {
      // Find the oldest currently-expanded card (last in sorted order among expanded).
      const currentExpanded = sorted.filter((c) => expandedIds.has(c.id));
      const oldest = currentExpanded[currentExpanded.length - 1];
      if (oldest) expandedIds.delete(oldest.id);
      expandedIds.add(id);
    }
  }

  const collapsed: Card[] = [];
  const expanded: Card[] = [];
  for (const card of cards) {
    if (expandedIds.has(card.id)) {
      expanded.push(card);
    } else {
      collapsed.push(card);
    }
  }
  return { collapsed, expanded };
}

export function MarginColumn({
  cards,
  visibleSids,
  focusedCardId,
  newlyCreatedNoteId,
  onBodyChange,
  onBodyCommit,
  leftSids,
  rightSids,
  leftFolio,
  rightFolio,
  currentSpreadSids,
  bookRoot,
  onJump,
  onFollowup,
  focusedComposerCardId,
}: {
  cards: Card[];
  visibleSids: Set<string>;
  focusedCardId: string | null;
  newlyCreatedNoteId?: string | null;
  onBodyChange: (id: string, next: string) => void;
  onBodyCommit: (id: string) => void;
  leftSids?: Set<string>;
  rightSids?: Set<string>;
  leftFolio?: number;
  rightFolio?: number;
  /** Sids only from the current spread (used to distinguish current vs previous spread cards). */
  currentSpreadSids?: Set<string>;
  bookRoot?: Element | null;
  onJump?: (sid: string) => void;
  onFollowup?: (cardId: string, question: string) => void;
  focusedComposerCardId?: string | null;
}) {
  const [manuallyExpandedIds, setManuallyExpandedIds] = useState<Set<string>>(
    new Set(),
  );

  const visible = cards.filter((c) => visibleSids.has(c.anchor));
  const { collapsed, expanded } = partitionWithOverrides(
    visible,
    manuallyExpandedIds,
  );

  const anchorSidsKey = visible.map((c) => c.anchor).sort().join(",");
  // Stable Set reference — only recreated when the set of anchors actually changes.
  const anchorSids = useMemo(
    () => new Set(visible.map((c) => c.anchor)),
    // anchorSidsKey is a derived primitive — safe to use as dep.
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [anchorSidsKey],
  );
  const anchorVisibility = useAnchorVisibility(
    anchorSids,
    bookRoot ?? null,
  );

  const handleExpand = useCallback(
    (id: string) => {
      setManuallyExpandedIds((prev) => {
        const next = new Set(prev);
        next.add(id);
        return next;
      });
    },
    [],
  );

  // Ref map for follow-up composers keyed by card id.
  const composerRefs = useRef<Map<string, HTMLInputElement>>(new Map());
  const setComposerRef = useCallback(
    (id: string) => (el: HTMLInputElement | null) => {
      if (el) {
        composerRefs.current.set(id, el);
      } else {
        composerRefs.current.delete(id);
      }
    },
    [],
  );

  // Focus the composer when focusedComposerCardId changes.
  useEffect(() => {
    if (!focusedComposerCardId) return;
    const el = composerRefs.current.get(focusedComposerCardId);
    if (el) el.focus();
  }, [focusedComposerCardId]);

  // Determine if any expanded card's anchor is off-screen (for AnchorEdgeBar).
  const offscreenDirections = expanded
    .map((card) => {
      const e = anchorVisibility.get(card.anchor);
      return e && !e.visible && e.direction ? e.direction : null;
    })
    .filter(Boolean) as ("up" | "down")[];
  const hasOffscreenUp = offscreenDirections.includes("up");
  const hasOffscreenDown = offscreenDirections.includes("down");

  // Compute AnchorConnector geometry for single-card case.
  const showConnector = expanded.length === 1 && bookRoot;
  let connectorFrom = { x: 0, y: 0 };
  let connectorTo = { x: 0, y: 0 };
  if (showConnector) {
    const card = expanded[0];
    const rect = getAnchorRect(bookRoot as Element, card.anchor);
    if (rect) {
      connectorTo = { x: rect.right, y: rect.top + rect.height / 2 };
      connectorFrom = { x: 0, y: rect.top + rect.height / 2 };
    }
  }

  return (
    <aside
      aria-label="Margin cards"
      data-testid="margin-column"
      style={{
        display: "flex",
        flexDirection: "column",
        gap: 14,
        paddingTop: 40,
        width: 400,
        position: "relative",
      }}
    >
      {visible.length === 0 && <S1EmptyCard />}

      {/* Collapsed rows */}
      {collapsed.map((card) => (
        <CollapsedCardRow key={card.id} card={card} onExpand={handleExpand} />
      ))}

      {/* Divider — only when there are collapsed cards */}
      {collapsed.length > 0 && <LatestExpandedDivider />}

      {/* Expanded cards */}
      {expanded.map((card) => {
        const visEntry = anchorVisibility.get(card.anchor);
        const offscreen =
          visEntry && !visEntry.visible && visEntry.direction
            ? { direction: visEntry.direction as "up" | "down" }
            : undefined;

        // Cross-page prefix: show "← FROM p. {folio}" when the card's anchor
        // is on the current spread's LEFT page (the margin column sits on the
        // right, so left-page anchors are "cross-page"). Only when not offscreen.
        let crossPage: { direction: "left" | "right"; folio: number } | undefined;
        if (!offscreen && leftSids && rightSids && leftFolio !== undefined && rightFolio !== undefined) {
          crossPage = computeCrossPage({
            sid: card.anchor,
            leftSids,
            rightSids,
            leftFolio,
            rightFolio,
          }) ?? undefined;
        }

        const handleJump = onJump ? () => onJump(card.anchor) : undefined;
        const handleFollowup = onFollowup
          ? (q: string) => onFollowup(card.id, q)
          : undefined;

        return card.kind === "ask" ? (
          <AskCard
            key={card.id}
            card={card}
            flash={focusedCardId === card.id}
            offscreen={offscreen}
            crossPage={crossPage}
            onJump={handleJump}
            onFollowup={handleFollowup}
            composerRef={setComposerRef(card.id)}
          />
        ) : (
          <NoteCard
            key={card.id}
            card={card}
            flash={focusedCardId === card.id}
            autoFocus={newlyCreatedNoteId === card.id}
            onBodyChange={onBodyChange}
            onBodyCommit={onBodyCommit}
            offscreen={offscreen}
            crossPage={crossPage}
            onJump={handleJump}
          />
        );
      })}

      {/* S6: AnchorEdgeBar — shown when any expanded card's anchor is off-screen */}
      {hasOffscreenUp && (
        <AnchorEdgeBar top={0} color="var(--accent)" />
      )}
      {hasOffscreenDown && (
        <AnchorEdgeBar top={200} color="var(--accent)" />
      )}

      {/* S2: AnchorConnector — only with exactly 1 expanded card */}
      {showConnector && (
        <AnchorConnector from={connectorFrom} to={connectorTo} />
      )}
    </aside>
  );
}
