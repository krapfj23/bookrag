import { useCallback, useEffect, useState } from "react";

export type ReadingMode = "on" | "off";

function storageKey(bookId: string): string {
  return `bookrag.reading-mode.${bookId}`;
}

function read(bookId: string): ReadingMode {
  try {
    const raw = localStorage.getItem(storageKey(bookId));
    if (raw == null) return "off";
    const parsed = JSON.parse(raw);
    return parsed === "on" ? "on" : "off";
  } catch {
    return "off";
  }
}

export function useReadingMode(bookId: string) {
  const [mode, setModeState] = useState<ReadingMode>(() => read(bookId));

  useEffect(() => {
    setModeState(read(bookId));
  }, [bookId]);

  const setMode = useCallback(
    (next: ReadingMode) => {
      setModeState(next);
      try {
        localStorage.setItem(storageKey(bookId), JSON.stringify(next));
      } catch {}
    },
    [bookId],
  );

  const toggle = useCallback(() => {
    setMode(mode === "on" ? "off" : "on");
  }, [mode, setMode]);

  return { mode, toggle, setMode };
}
