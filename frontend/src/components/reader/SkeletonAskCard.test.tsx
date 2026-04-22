import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { SkeletonAskCard } from "./SkeletonAskCard";
import { BlinkingCursor } from "./BlinkingCursor";

describe("SkeletonAskCard", () => {
  it("renders the S3 thinking skeleton with header copy", () => {
    render(<SkeletonAskCard />);
    const card = screen.getByTestId("skeleton-ask-card");
    expect(card).toBeInTheDocument();
    expect(card.textContent ?? "").toMatch(/THINKING/i);
    expect(card.textContent ?? "").toMatch(/gathering 3 more passages/i);
  });

  it("renders two shimmer placeholder lines", () => {
    const { container } = render(<SkeletonAskCard />);
    const shimmerEls = container.querySelectorAll(
      '[data-testid="skeleton-shimmer"]',
    );
    expect(shimmerEls.length).toBe(2);
  });
});

describe("BlinkingCursor", () => {
  it("renders a blinking cursor element with the expected testid", () => {
    render(<BlinkingCursor />);
    const el = screen.getByTestId("blinking-cursor");
    expect(el).toBeInTheDocument();
  });

  it("applies the blink animation and 6x14 dimensions via inline style", () => {
    render(<BlinkingCursor />);
    const el = screen.getByTestId("blinking-cursor") as HTMLElement;
    const style = el.getAttribute("style") ?? "";
    expect(style).toMatch(/animation:\s*blink/);
    expect(style).toMatch(/1s/);
    expect(style).toMatch(/width:\s*6px/);
    expect(style).toMatch(/height:\s*14px/);
  });
});
