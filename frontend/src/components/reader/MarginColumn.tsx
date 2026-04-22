import { useCallback, useState } from "react";
import type { Card } from "../../lib/reader/cards";
import { AskCard } from "./AskCard";
import { NoteCard } from "./NoteCard";
import { S1EmptyCard } from "./S1EmptyCard";
import { CollapsedCardRow } from "./CollapsedCardRow";
import { LatestExpandedDivider } from "./LatestExpandedDivider";
import { AnchorConnector } from "./AnchorConnector";
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
  bookRoot,
  onJump,
  onFollowup,
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
  bookRoot?: Element | null;
  onJump?: (sid: string) => void;
  onFollowup?: (cardId: string, question: string) => void;
}) {
  const [manuallyExpandedIds, setManuallyExpandedIds] = useState<Set<string>>(
    new Set(),
  );

  const visible = cards.filter((c) => visibleSids.has(c.anchor));
  const { collapsed, expanded } = partitionWithOverrides(
    visible,
    manuallyExpandedIds,
  );

  const anchorSids = new Set(visible.map((c) => c.anchor));
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

        const crossPage =
          leftSids && rightSids && leftFolio !== undefined && rightFolio !== undefined
            ? computeCrossPage({
                sid: card.anchor,
                leftSids,
                rightSids,
                leftFolio,
                rightFolio,
              }) ?? undefined
            : undefined;

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

      {/* S2: AnchorConnector — only with exactly 1 expanded card */}
      {showConnector && (
        <AnchorConnector from={connectorFrom} to={connectorTo} />
      )}
    </aside>
  );
}
