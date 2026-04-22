import { describe, it, expect } from "vitest";
import { computeSelection } from "./selection";

function setupDom(): HTMLElement {
  const root = document.createElement("div");
  root.innerHTML = `
    <p>
      <span data-sid="p1.s1">Alpha sentence.</span>
      <span data-sid="p1.s2">Bravo sentence.</span>
    </p>`;
  document.body.appendChild(root);
  return root;
}

describe("computeSelection", () => {
  it("returns null for collapsed selection", () => {
    const root = setupDom();
    const range = document.createRange();
    const target = root.querySelector('[data-sid="p1.s1"]')!;
    range.setStart(target.firstChild!, 0);
    range.setEnd(target.firstChild!, 0);
    expect(computeSelection(range, root)).toBeNull();
  });

  it("returns anchorSid from range start and exact quote text", () => {
    const root = setupDom();
    const span = root.querySelector('[data-sid="p1.s1"]')!;
    const text = span.firstChild as Text;
    const range = document.createRange();
    range.setStart(text, 0);
    range.setEnd(text, 5); // "Alpha"
    const res = computeSelection(range, root);
    expect(res).not.toBeNull();
    expect(res!.anchorSid).toBe("p1.s1");
    expect(res!.quote).toBe("Alpha");
  });

  it("returns null when range is outside the container", () => {
    const root = setupDom();
    const outside = document.createElement("span");
    document.body.appendChild(outside);
    outside.textContent = "x";
    const range = document.createRange();
    range.setStart(outside.firstChild!, 0);
    range.setEnd(outside.firstChild!, 1);
    expect(computeSelection(range, root)).toBeNull();
  });
});
