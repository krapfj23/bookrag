import type { Card } from "./cards";

export interface OverflowPartition {
  collapsed: Card[];
  expanded: Card[];
}

/**
 * Partition cards so the 2 most recently updated are "expanded"
 * and the rest are "collapsed". Input order is preserved within each group.
 */
export function partitionForOverflow(cards: Card[]): OverflowPartition {
  if (cards.length <= 2) {
    return { collapsed: [], expanded: [...cards] };
  }
  // Sort by updatedAt descending to find the 2 newest.
  const sorted = [...cards].sort(
    (a, b) => new Date(b.updatedAt).getTime() - new Date(a.updatedAt).getTime(),
  );
  const expandedIds = new Set([sorted[0].id, sorted[1].id]);

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

/**
 * Extracts the paragraph number from a sid like "p{n}.s{m}".
 * Returns NaN if the format doesn't match.
 */
export function getFolioFromAnchor(anchor: string): number {
  const m = anchor.match(/^p(\d+)\./);
  return m ? parseInt(m[1], 10) : NaN;
}
