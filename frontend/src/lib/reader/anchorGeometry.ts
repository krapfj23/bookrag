/**
 * Returns the bounding client rect of the element with [data-sid="{sid}"]
 * inside the given root, or null if not found.
 */
export function getAnchorRect(
  root: Element | null,
  sid: string,
): DOMRect | null {
  if (!root) return null;
  const el = root.querySelector(`[data-sid="${sid}"]`);
  if (!el) return null;
  return el.getBoundingClientRect();
}
