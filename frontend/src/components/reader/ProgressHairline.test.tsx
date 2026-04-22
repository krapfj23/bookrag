import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { ProgressHairline } from "./ProgressHairline";

function innerWidth(container: HTMLElement): string {
  const fg = container.firstElementChild as HTMLElement | null;
  return fg ? fg.style.width : "";
}

describe("ProgressHairline", () => {
  it("renders testid and inner width matches formula (0.25 → 25%)", () => {
    render(<ProgressHairline progress={0.25} />);
    const el = screen.getByTestId("progress-hairline");
    expect(innerWidth(el)).toBe("25%");
  });

  it("formats non-round fractions via Math.round(progress*10000)/100 (0.12345 → 12.35%)", () => {
    render(<ProgressHairline progress={0.12345} />);
    const el = screen.getByTestId("progress-hairline");
    expect(innerWidth(el)).toBe("12.35%");
  });

  it("clamps negative progress to 0%", () => {
    render(<ProgressHairline progress={-0.5} />);
    const el = screen.getByTestId("progress-hairline");
    expect(innerWidth(el)).toBe("0%");
  });

  it("clamps >1 progress to 100%", () => {
    render(<ProgressHairline progress={1.5} />);
    const el = screen.getByTestId("progress-hairline");
    expect(innerWidth(el)).toBe("100%");
  });
});
