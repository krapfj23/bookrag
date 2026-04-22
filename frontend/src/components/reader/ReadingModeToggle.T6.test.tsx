/**
 * T6 — ReadingModeToggle padding/radius/border.
 */
import { describe, it, expect } from "vitest";
import { render } from "@testing-library/react";
import { ReadingModeToggle } from "./ReadingModeToggle";

describe("ReadingModeToggle T6 — visual spec", () => {
  it("has padding 5px 12px in inline style (off state)", () => {
    const { getByRole } = render(
      <ReadingModeToggle mode="off" onToggle={() => {}} />
    );
    const btn = getByRole("button");
    const style = btn.getAttribute("style") ?? "";
    expect(style).toMatch(/padding:\s*5px 12px/);
  });

  it("has border-radius 999px", () => {
    const { getByRole } = render(
      <ReadingModeToggle mode="off" onToggle={() => {}} />
    );
    const btn = getByRole("button");
    const style = btn.getAttribute("style") ?? "";
    expect(style).toMatch(/border-radius:\s*999px/);
  });

  it("has no border (border: none or border-width: 0px)", () => {
    const { getByRole } = render(
      <ReadingModeToggle mode="off" onToggle={() => {}} />
    );
    const btn = getByRole("button");
    const style = btn.getAttribute("style") ?? "";
    // Border should be absent or explicitly 0/none
    const hasNoExplicitBorder =
      !style.includes("border:") ||
      style.includes("border: 0") ||
      style.includes("border-width: 0");
    expect(hasNoExplicitBorder).toBe(true);
  });
});
