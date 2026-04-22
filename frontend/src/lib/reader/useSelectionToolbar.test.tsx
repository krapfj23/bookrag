import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { renderHook, act } from "@testing-library/react";
import { useSelectionToolbar } from "./useSelectionToolbar";
import { useRef, useEffect } from "react";

describe("useSelectionToolbar", () => {
  beforeEach(() => vi.useFakeTimers());
  afterEach(() => vi.useRealTimers());

  it("returns null when nothing is selected", () => {
    const container = document.createElement("div");
    container.innerHTML = '<span data-sid="p1.s1">Hi there.</span>';
    document.body.appendChild(container);
    const { result } = renderHook(() => {
      const ref = useRef<HTMLElement | null>(null);
      useEffect(() => {
        ref.current = container;
      }, []);
      return useSelectionToolbar(ref);
    });
    expect(result.current.selection).toBeNull();
  });

  it("captures selection anchor sid on selectionchange", async () => {
    const container = document.createElement("div");
    container.innerHTML = '<span data-sid="p1.s1">Hi there.</span>';
    document.body.appendChild(container);
    const ref = { current: container } as React.MutableRefObject<HTMLElement | null>;
    const { result } = renderHook(() => useSelectionToolbar(ref));
    const span = container.querySelector("[data-sid]")!;
    const range = document.createRange();
    range.setStart(span.firstChild!, 0);
    range.setEnd(span.firstChild!, 2);
    const sel = window.getSelection()!;
    sel.removeAllRanges();
    sel.addRange(range);
    act(() => {
      document.dispatchEvent(new Event("selectionchange"));
      vi.advanceTimersByTime(120);
    });
    expect(result.current.selection).not.toBeNull();
    expect(result.current.selection!.anchorSid).toBe("p1.s1");
    expect(result.current.selection!.quote).toBe("Hi");
  });
});
