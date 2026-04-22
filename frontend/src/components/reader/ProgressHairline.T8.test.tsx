/**
 * T8 — ProgressHairline track background uses --paper-2.
 */
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { ProgressHairline } from "./ProgressHairline";

describe("ProgressHairline T8 — track color", () => {
  it("track root uses var(--paper-2) as background", () => {
    render(<ProgressHairline progress={0.5} />);
    const track = screen.getByTestId("progress-hairline");
    const style = track.getAttribute("style") ?? "";
    expect(style).toContain("var(--paper-2)");
  });
});
