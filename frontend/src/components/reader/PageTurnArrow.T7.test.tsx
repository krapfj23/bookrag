/**
 * T7 — PageTurnArrow: circular 48px, opacity 0.5, IcArrow icons.
 */
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { PageTurnArrow } from "./PageTurnArrow";

describe("PageTurnArrow T7 — visual spec", () => {
  it("right arrow has width 48px and height 48px in style", () => {
    render(<PageTurnArrow direction="right" onClick={() => {}} />);
    const btn = screen.getByTestId("page-arrow-right");
    const style = btn.getAttribute("style") ?? "";
    expect(style).toMatch(/width:\s*48px/);
    expect(style).toMatch(/height:\s*48px/);
  });

  it("has border-radius 999px", () => {
    render(<PageTurnArrow direction="right" onClick={() => {}} />);
    const btn = screen.getByTestId("page-arrow-right");
    const style = btn.getAttribute("style") ?? "";
    expect(style).toMatch(/border-radius:\s*999px/);
  });

  it("has base opacity 0.5", () => {
    render(<PageTurnArrow direction="right" onClick={() => {}} />);
    const btn = screen.getByTestId("page-arrow-right");
    const style = btn.getAttribute("style") ?? "";
    expect(style).toMatch(/opacity:\s*0\.5/);
  });

  it("renders an SVG icon (not a text glyph)", () => {
    render(<PageTurnArrow direction="right" onClick={() => {}} />);
    const btn = screen.getByTestId("page-arrow-right");
    const svg = btn.querySelector("svg");
    expect(svg).not.toBeNull();
  });
});
