import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import { ProgressPill } from "./ProgressPill";

describe("ProgressPill", () => {
  it("renders '<current> of <total>'", () => {
    render(<ProgressPill current={2} total={3} />);
    expect(screen.getByText("2")).toBeInTheDocument();
    expect(screen.getByText(/of\s*3/i)).toBeInTheDocument();
  });

  it("clamps width to 100% when current exceeds total", () => {
    const { container } = render(<ProgressPill current={10} total={3} />);
    const bar = container.querySelector("[data-pill-fill]") as HTMLElement;
    expect(bar).toBeTruthy();
    expect(bar.style.width).toBe("100%");
  });

  it("renders 0% width when current is 0", () => {
    const { container } = render(<ProgressPill current={0} total={3} />);
    const bar = container.querySelector("[data-pill-fill]") as HTMLElement;
    expect(bar.style.width).toBe("0%");
  });
});
