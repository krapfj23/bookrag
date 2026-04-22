import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { renderHook, act } from "@testing-library/react";
import { useAnchorVisibility } from "./useAnchorVisibility";

type Entry = {
  target: Element;
  isIntersecting: boolean;
  boundingClientRect: { top: number; bottom: number };
};

let lastCallback: ((entries: Entry[]) => void) | null = null;
let observed: Element[] = [];

class FakeIntersectionObserver {
  constructor(cb: (entries: Entry[]) => void) {
    lastCallback = cb;
  }
  observe(el: Element) {
    observed.push(el);
  }
  unobserve() {}
  disconnect() {
    observed = [];
  }
  takeRecords() {
    return [];
  }
}

describe("useAnchorVisibility", () => {
  beforeEach(() => {
    document.body.innerHTML = "";
    lastCallback = null;
    observed = [];
    (globalThis as unknown as { IntersectionObserver: unknown }).IntersectionObserver =
      FakeIntersectionObserver as unknown as typeof IntersectionObserver;
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("reports direction 'up' for elements above the viewport", () => {
    const root = document.createElement("div");
    const a = document.createElement("span");
    a.setAttribute("data-sid", "p1.s1");
    root.appendChild(a);
    document.body.appendChild(root);

    const { result } = renderHook(() =>
      useAnchorVisibility(new Set(["p1.s1"]), root),
    );

    act(() => {
      lastCallback!([
        {
          target: a,
          isIntersecting: false,
          boundingClientRect: { top: -200, bottom: -100 },
        },
      ]);
    });
    const entry = result.current.get("p1.s1");
    expect(entry).toBeDefined();
    expect(entry!.visible).toBe(false);
    expect(entry!.direction).toBe("up");
  });

  it("reports direction 'down' for elements below the viewport", () => {
    const root = document.createElement("div");
    const a = document.createElement("span");
    a.setAttribute("data-sid", "p1.s2");
    root.appendChild(a);
    document.body.appendChild(root);

    // @ts-expect-error jsdom lacks innerHeight setter semantics; assign directly.
    window.innerHeight = 600;

    const { result } = renderHook(() =>
      useAnchorVisibility(new Set(["p1.s2"]), root),
    );
    act(() => {
      lastCallback!([
        {
          target: a,
          isIntersecting: false,
          boundingClientRect: { top: 1000, bottom: 1100 },
        },
      ]);
    });
    const entry = result.current.get("p1.s2");
    expect(entry!.visible).toBe(false);
    expect(entry!.direction).toBe("down");
  });

  it("reports visible=true with direction=null when element intersects", () => {
    const root = document.createElement("div");
    const a = document.createElement("span");
    a.setAttribute("data-sid", "p1.s3");
    root.appendChild(a);
    document.body.appendChild(root);

    const { result } = renderHook(() =>
      useAnchorVisibility(new Set(["p1.s3"]), root),
    );
    act(() => {
      lastCallback!([
        {
          target: a,
          isIntersecting: true,
          boundingClientRect: { top: 100, bottom: 150 },
        },
      ]);
    });
    const entry = result.current.get("p1.s3");
    expect(entry!.visible).toBe(true);
    expect(entry!.direction).toBeNull();
  });
});
