/**
 * T9 — PacingLabel styling: 12px, uppercase, 1.4px letter-spacing.
 */
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { PacingLabel } from "./PacingLabel";

describe("PacingLabel T9 — visual spec", () => {
  it("has font-size 12px in inline style", () => {
    render(<PacingLabel num={1} total={5} />);
    const el = screen.getByTestId("pacing-label");
    const style = el.getAttribute("style") ?? "";
    expect(style).toMatch(/font-size:\s*12px/);
  });

  it("has text-transform uppercase in inline style", () => {
    render(<PacingLabel num={1} total={5} />);
    const el = screen.getByTestId("pacing-label");
    const style = el.getAttribute("style") ?? "";
    expect(style).toMatch(/text-transform:\s*uppercase/);
  });

  it("has letter-spacing 1.4px in inline style", () => {
    render(<PacingLabel num={1} total={5} />);
    const el = screen.getByTestId("pacing-label");
    const style = el.getAttribute("style") ?? "";
    expect(style).toMatch(/letter-spacing:\s*1\.4px/);
  });
});
