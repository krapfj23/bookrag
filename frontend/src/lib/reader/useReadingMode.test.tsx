import { describe, it, expect, beforeEach } from "vitest";
import { act, renderHook } from "@testing-library/react";
import { useReadingMode } from "./useReadingMode";

describe("useReadingMode", () => {
  beforeEach(() => localStorage.clear());

  it("defaults to off when no key present", () => {
    const { result } = renderHook(() => useReadingMode("book-a"));
    expect(result.current.mode).toBe("off");
  });

  it("reads persisted value for the bookId", () => {
    localStorage.setItem("bookrag.reading-mode.book-a", JSON.stringify("on"));
    const { result } = renderHook(() => useReadingMode("book-a"));
    expect(result.current.mode).toBe("on");
  });

  it("toggle flips and persists under per-book key", () => {
    const { result } = renderHook(() => useReadingMode("book-a"));
    act(() => result.current.toggle());
    expect(result.current.mode).toBe("on");
    expect(localStorage.getItem("bookrag.reading-mode.book-a")).toBe('"on"');
    act(() => result.current.toggle());
    expect(result.current.mode).toBe("off");
    expect(localStorage.getItem("bookrag.reading-mode.book-a")).toBe('"off"');
  });

  it("two books are isolated", () => {
    const a = renderHook(() => useReadingMode("book-a"));
    const b = renderHook(() => useReadingMode("book-b"));
    act(() => a.result.current.toggle());
    expect(a.result.current.mode).toBe("on");
    expect(b.result.current.mode).toBe("off");
  });

  it("ignores malformed JSON and defaults to off", () => {
    localStorage.setItem("bookrag.reading-mode.book-a", "not-json");
    const { result } = renderHook(() => useReadingMode("book-a"));
    expect(result.current.mode).toBe("off");
  });
});
