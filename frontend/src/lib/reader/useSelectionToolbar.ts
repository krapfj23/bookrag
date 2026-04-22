import { useEffect, useRef, useState, type MutableRefObject } from "react";
import { computeSelection, type ComputedSelection } from "./selection";

export function useSelectionToolbar(
  containerRef: MutableRefObject<HTMLElement | null>,
) {
  const [selection, setSelection] = useState<ComputedSelection | null>(null);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    function schedule() {
      if (timer.current) clearTimeout(timer.current);
      timer.current = setTimeout(() => {
        const container = containerRef.current;
        if (!container) {
          setSelection(null);
          return;
        }
        const sel = window.getSelection();
        if (!sel || sel.rangeCount === 0) {
          setSelection(null);
          return;
        }
        const range = sel.getRangeAt(0);
        setSelection(computeSelection(range, container));
      }, 100);
    }
    document.addEventListener("selectionchange", schedule);
    return () => {
      document.removeEventListener("selectionchange", schedule);
      if (timer.current) clearTimeout(timer.current);
    };
  }, [containerRef]);

  return {
    selection,
    clear: () => {
      window.getSelection()?.removeAllRanges();
      setSelection(null);
    },
  };
}
