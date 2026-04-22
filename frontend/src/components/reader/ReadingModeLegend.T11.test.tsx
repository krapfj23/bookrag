/**
 * T11 — ReadingModeLegend font-size 10.5px.
 */
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { ReadingModeLegend } from "./ReadingModeLegend";

describe("ReadingModeLegend T11 — font size", () => {
  it("root element has font-size 10.5px in inline style", () => {
    render(<ReadingModeLegend />);
    const el = screen.getByTestId("reading-mode-legend") as HTMLElement;
    const style = el.getAttribute("style") ?? "";
    expect(style).toMatch(/font-size:\s*10\.5px/);
  });
});
