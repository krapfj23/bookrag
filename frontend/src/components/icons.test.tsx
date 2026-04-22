/**
 * T4 — Icon path accuracy tests.
 * Verifies that each icon renders the exact path strings from the design handoff.
 */
import { describe, it, expect } from "vitest";
import { render } from "@testing-library/react";
import { IcSpark, IcSend, IcHighlight, IcChevron } from "./icons";

describe("IcSpark", () => {
  it("renders the handoff path d attribute", () => {
    const { container } = render(<IcSpark />);
    const path = container.querySelector("path");
    expect(path).not.toBeNull();
    expect(path!.getAttribute("d")).toBe(
      "M8 2v3M8 11v3M2 8h3M11 8h3M4 4l2 2M10 10l2 2M12 4l-2 2M4 12l2-2"
    );
  });
});

describe("IcSend", () => {
  it("renders the handoff path d attribute", () => {
    const { container } = render(<IcSend />);
    const path = container.querySelector("path");
    expect(path).not.toBeNull();
    expect(path!.getAttribute("d")).toBe("M13.5 2.5L2.5 7l5 1.5L9 13.5l4.5-11z");
  });
});

describe("IcHighlight", () => {
  it("renders the handoff path d attribute", () => {
    const { container } = render(<IcHighlight />);
    const path = container.querySelector("path");
    expect(path).not.toBeNull();
    // Handoff IcHighlight path from icons.jsx line 32
    expect(path!.getAttribute("d")).toBe("M3 13h10M4.5 10.5l3 3 6-6-3-3-6 6z");
  });
});

describe("IcChevron", () => {
  it("is exported and renders path d=M4 6l4 4 4-4", () => {
    const { container } = render(<IcChevron />);
    const path = container.querySelector("path");
    expect(path).not.toBeNull();
    expect(path!.getAttribute("d")).toBe("M4 6l4 4 4-4");
  });
});
