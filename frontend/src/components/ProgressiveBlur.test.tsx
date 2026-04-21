import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import { ProgressiveBlur } from "./ProgressiveBlur";

describe("ProgressiveBlur", () => {
  it("renders its children", () => {
    render(
      <ProgressiveBlur locked={false}>
        <p>Visible paragraph</p>
      </ProgressiveBlur>
    );
    expect(screen.getByText("Visible paragraph")).toBeInTheDocument();
  });

  it("when locked, overlays a blur + CTA pill", () => {
    render(
      <ProgressiveBlur locked>
        <p>Hidden-ish</p>
      </ProgressiveBlur>
    );
    expect(screen.getByText(/advance to reveal/i)).toBeInTheDocument();
    expect(screen.getByText("Hidden-ish")).toBeInTheDocument();
  });

  it("when unlocked, omits the CTA pill", () => {
    render(
      <ProgressiveBlur locked={false}>
        <p>Open</p>
      </ProgressiveBlur>
    );
    expect(screen.queryByText(/advance to reveal/i)).toBeNull();
  });
});
