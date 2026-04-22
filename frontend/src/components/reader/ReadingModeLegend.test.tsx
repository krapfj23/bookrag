import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { ReadingModeLegend } from "./ReadingModeLegend";

describe("ReadingModeLegend", () => {
  it("renders testid reading-mode-legend containing ASKED, NOTED, ENTITY", () => {
    render(<ReadingModeLegend />);
    const el = screen.getByTestId("reading-mode-legend");
    expect(el.textContent ?? "").toContain("ASKED");
    expect(el.textContent ?? "").toContain("NOTED");
    expect(el.textContent ?? "").toContain("ENTITY");
  });
});
