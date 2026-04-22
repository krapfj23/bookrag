import { useCallback, useEffect, useState } from "react";
import { compareSid } from "./sidCompare";

export const CURSOR_KEY = (bookId: string) => `bookrag.cursor.${bookId}`;

export type StoredCursor = { chapter: number; anchor: string };

export function readStoredCursor(bookId: string): StoredCursor | null {
  try {
    const raw = window.localStorage.getItem(CURSOR_KEY(bookId));
    if (!raw) return null;
    const v = JSON.parse(raw);
    if (typeof v?.chapter === "number" && typeof v?.anchor === "string") return v;
    return null;
  } catch {
    return null;
  }
}

export function useReadingCursor(
  bookId: string,
  chapter: number,
  firstSid: string,
) {
  const [cursor, setCursor] = useState<string>(() => {
    const stored = readStoredCursor(bookId);
    if (stored && stored.chapter === chapter) return stored.anchor;
    return firstSid;
  });

  // If bookId or chapter changes, re-seed from storage or firstSid.
  useEffect(() => {
    const stored = readStoredCursor(bookId);
    if (stored && stored.chapter === chapter) setCursor(stored.anchor);
    else setCursor(firstSid);
  }, [bookId, chapter, firstSid]);

  const advanceTo = useCallback(
    (sid: string) => {
      setCursor((prev) => {
        if (compareSid(sid, prev) <= 0) return prev;
        try {
          window.localStorage.setItem(
            CURSOR_KEY(bookId),
            JSON.stringify({ chapter, anchor: sid }),
          );
        } catch {
          /* ignore quota */
        }
        return sid;
      });
    },
    [bookId, chapter],
  );

  return { cursor, advanceTo };
}
