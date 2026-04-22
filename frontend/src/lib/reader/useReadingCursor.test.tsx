/**
 * @vitest-environment jsdom
 */
import { describe, it, expect, beforeEach } from "vitest";
import { renderHook, act } from "@testing-library/react";
import { useReadingCursor, readStoredCursor, CURSOR_KEY } from "./useReadingCursor";

describe("useReadingCursor", () => {
  beforeEach(() => window.localStorage.clear());

  it("initializes to firstSid when no stored value", () => {
    const { result } = renderHook(() =>
      useReadingCursor("bk", 1, "p1.s1"),
    );
    expect(result.current.cursor).toBe("p1.s1");
  });

  it("advances forward only", () => {
    const { result } = renderHook(() =>
      useReadingCursor("bk", 1, "p1.s1"),
    );
    act(() => result.current.advanceTo("p2.s3"));
    expect(result.current.cursor).toBe("p2.s3");
    // Backward call must not rewind.
    act(() => result.current.advanceTo("p1.s5"));
    expect(result.current.cursor).toBe("p2.s3");
  });

  it("persists to localStorage under bookrag.cursor.{bookId}", () => {
    const { result } = renderHook(() =>
      useReadingCursor("bk", 1, "p1.s1"),
    );
    act(() => result.current.advanceTo("p3.s2"));
    const raw = window.localStorage.getItem(CURSOR_KEY("bk"));
    expect(raw).not.toBeNull();
    const parsed = JSON.parse(raw!);
    expect(parsed).toEqual({ chapter: 1, anchor: "p3.s2" });
  });

  it("restores from localStorage", () => {
    window.localStorage.setItem(
      CURSOR_KEY("bk"),
      JSON.stringify({ chapter: 1, anchor: "p4.s1" }),
    );
    expect(readStoredCursor("bk")).toEqual({ chapter: 1, anchor: "p4.s1" });
    const { result } = renderHook(() =>
      useReadingCursor("bk", 1, "p1.s1"),
    );
    expect(result.current.cursor).toBe("p4.s1");
  });
});
