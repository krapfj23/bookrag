/**
 * T13 — Skeleton card header-label text.
 * Verifies exact text "THINKING · gathering 3 more passages".
 */
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { SkeletonAskCard } from "./SkeletonAskCard";

describe("SkeletonAskCard T13 — thinking header strip", () => {
  it("renders the exact THINKING header text", () => {
    render(<SkeletonAskCard />);
    const card = screen.getByTestId("skeleton-ask-card");
    expect(card.textContent).toMatch(/THINKING · gathering 3 more passages/);
  });
});
