export interface CrossPageResult {
  direction: "left" | "right";
  folio: number;
}

export interface ComputeCrossPageInput {
  sid: string;
  leftSids: Set<string>;
  rightSids: Set<string>;
  leftFolio: number;
  rightFolio: number;
}

/**
 * Returns cross-page info if the anchor is on the left page (the margin column
 * sits on the right, so left-page anchors are "cross-page" from the card).
 * Returns null if the anchor is on the right page or not found on either.
 */
export function computeCrossPage(
  input: ComputeCrossPageInput,
): CrossPageResult | null {
  const { sid, leftSids, leftFolio } = input;
  if (leftSids.has(sid)) {
    return { direction: "left", folio: leftFolio };
  }
  // Right page anchors are "same side" as the margin column — no prefix.
  return null;
}
