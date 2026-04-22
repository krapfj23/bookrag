export interface ComputedSelection {
  anchorSid: string;
  quote: string;
  rect: DOMRect;
}

function findSidAncestor(node: Node | null): string | null {
  let cur: Node | null = node;
  while (cur) {
    if (cur instanceof HTMLElement) {
      const sid = cur.getAttribute("data-sid");
      if (sid) return sid;
    }
    cur = cur.parentNode;
  }
  return null;
}

export function computeSelection(
  range: Range,
  container: HTMLElement,
): ComputedSelection | null {
  if (range.collapsed) return null;
  // Require both endpoints to live inside the container.
  if (
    !container.contains(range.startContainer) ||
    !container.contains(range.endContainer)
  ) {
    return null;
  }
  const anchorSid = findSidAncestor(range.startContainer);
  if (!anchorSid) return null;
  const quote = range.toString().trim();
  if (!quote) return null;
  const rect = range.getBoundingClientRect?.() ?? new DOMRect();
  return { anchorSid, quote, rect };
}
