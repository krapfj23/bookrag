import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { AnchorConnector } from "./AnchorConnector";

describe("AnchorConnector", () => {
  it("renders an SVG path with testid anchor-connector", () => {
    render(
      <AnchorConnector
        from={{ x: 100, y: 50 }}
        to={{ x: 300, y: 80 }}
      />,
    );
    const svg = screen.getByTestId("anchor-connector");
    expect(svg.tagName.toLowerCase()).toBe("svg");
    const path = svg.querySelector("path");
    expect(path).not.toBeNull();
  });

  it("path d attribute begins at 'from' point", () => {
    render(
      <AnchorConnector
        from={{ x: 100, y: 50 }}
        to={{ x: 300, y: 80 }}
      />,
    );
    const path = screen
      .getByTestId("anchor-connector")
      .querySelector("path")!;
    const d = path.getAttribute("d") ?? "";
    expect(d.startsWith("M 100 50") || d.startsWith("M100 50")).toBe(true);
    expect(d).toContain("300");
    expect(d).toContain("80");
  });

  it("uses dashed stroke with var(--accent) at ~0.6 opacity", () => {
    render(
      <AnchorConnector
        from={{ x: 10, y: 10 }}
        to={{ x: 20, y: 20 }}
      />,
    );
    const path = screen
      .getByTestId("anchor-connector")
      .querySelector("path")! as SVGPathElement;
    const dashArray = path.getAttribute("stroke-dasharray") ?? "";
    expect(dashArray).not.toBe("");
    const stroke = path.getAttribute("stroke") ?? "";
    expect(stroke).toMatch(/var\(--accent\)/);
    const opacity = path.getAttribute("stroke-opacity") ?? "";
    expect(parseFloat(opacity)).toBeCloseTo(0.6, 1);
  });

  it("is rendered with pointer-events:none so it doesn't block interactions", () => {
    render(
      <AnchorConnector
        from={{ x: 0, y: 0 }}
        to={{ x: 10, y: 10 }}
      />,
    );
    const svg = screen.getByTestId("anchor-connector") as SVGElement;
    const style = svg.getAttribute("style") ?? "";
    expect(style).toMatch(/pointer-events:\s*none/);
  });
});
