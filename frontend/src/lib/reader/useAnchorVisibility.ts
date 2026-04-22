import { useEffect, useState } from "react";

export interface AnchorVisibilityEntry {
  visible: boolean;
  direction: "up" | "down" | null;
  top: number;
}

/**
 * Observes each sid's [data-sid] element inside root via IntersectionObserver
 * and returns a Map of sid → { visible, direction, top }.
 */
export function useAnchorVisibility(
  sids: Set<string>,
  root: Element | null,
): Map<string, AnchorVisibilityEntry> {
  const [state, setState] = useState<Map<string, AnchorVisibilityEntry>>(
    new Map(),
  );

  useEffect(() => {
    if (!root) return;
    if (typeof IntersectionObserver === "undefined") return;

    const observer = new IntersectionObserver((entries) => {
      setState((prev) => {
        const next = new Map(prev);
        for (const entry of entries) {
          const el = entry.target as HTMLElement;
          const sid = el.dataset.sid;
          if (!sid) continue;
          const { top } = entry.boundingClientRect;
          let direction: "up" | "down" | null = null;
          if (!entry.isIntersecting) {
            direction = top < 0 ? "up" : "down";
          }
          next.set(sid, { visible: entry.isIntersecting, direction, top });
        }
        return next;
      });
    });

    const elements: Element[] = [];
    for (const sid of sids) {
      const el = root.querySelector(`[data-sid="${sid}"]`);
      if (el) {
        observer.observe(el);
        elements.push(el);
      }
    }

    return () => {
      observer.disconnect();
    };
  }, [sids, root]);

  return state;
}
