import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { PacingLabel } from "./PacingLabel";

const RE = /^stave (one|two|three|four|five|six|seven|eight|nine|ten|\d+) · of (one|two|three|four|five|six|seven|eight|nine|ten|\d+)$/i;

describe("PacingLabel", () => {
  it("renders 'Stave One · of Five' for (1, 5)", () => {
    render(<PacingLabel num={1} total={5} />);
    const el = screen.getByTestId("pacing-label");
    expect(el.textContent ?? "").toMatch(RE);
    expect(el.textContent ?? "").toMatch(/one/i);
    expect(el.textContent ?? "").toMatch(/five/i);
  });

  it("falls back to numeric when out-of-range (12, 20)", () => {
    render(<PacingLabel num={12} total={20} />);
    const el = screen.getByTestId("pacing-label");
    expect(el.textContent ?? "").toMatch(RE);
    expect(el.textContent ?? "").toMatch(/12/);
    expect(el.textContent ?? "").toMatch(/20/);
  });

  it("renders 'Stave Three · of Three' for (3, 3)", () => {
    render(<PacingLabel num={3} total={3} />);
    const el = screen.getByTestId("pacing-label");
    expect(el.textContent ?? "").toMatch(RE);
    expect((el.textContent ?? "").toLowerCase()).toContain("three");
  });
});
