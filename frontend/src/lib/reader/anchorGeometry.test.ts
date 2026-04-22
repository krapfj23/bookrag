import { describe, it, expect, beforeEach } from "vitest";
import { getAnchorRect } from "./anchorGeometry";

describe("getAnchorRect", () => {
  beforeEach(() => {
    document.body.innerHTML = "";
  });

  it("returns the bounding rect of the matching [data-sid] element", () => {
    const root = document.createElement("div");
    const s = document.createElement("span");
    s.setAttribute("data-sid", "p1.s1");
    s.textContent = "hi";
    root.appendChild(s);
    document.body.appendChild(root);
    const rect = getAnchorRect(root, "p1.s1");
    expect(rect).not.toBeNull();
    // JSDOM returns a DOMRect — fields must exist.
    expect(typeof rect!.top).toBe("number");
    expect(typeof rect!.left).toBe("number");
  });

  it("returns null when no element has the sid", () => {
    const root = document.createElement("div");
    document.body.appendChild(root);
    expect(getAnchorRect(root, "p9.s9")).toBeNull();
  });

  it("returns null when the root is null", () => {
    expect(getAnchorRect(null, "p1.s1")).toBeNull();
  });
});
