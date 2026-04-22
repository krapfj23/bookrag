import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ReadingModeToggle } from "./ReadingModeToggle";

describe("ReadingModeToggle", () => {
  it("renders off state with data-state=off and label 'Reading mode'", () => {
    render(<ReadingModeToggle mode="off" onToggle={() => {}} />);
    const btn = screen.getByRole("button", { name: /reading mode/i });
    expect(btn.getAttribute("data-state")).toBe("off");
    expect(btn.textContent).toMatch(/reading mode/i);
  });

  it("renders on state with data-state=on, checkmark, and 'Reading' text", () => {
    render(<ReadingModeToggle mode="on" onToggle={() => {}} />);
    const btn = screen.getByRole("button", { name: /reading mode/i });
    expect(btn.getAttribute("data-state")).toBe("on");
    expect(btn.textContent ?? "").toMatch(/Reading/);
    expect(btn.textContent ?? "").toContain("✓");
  });

  it("fires onToggle when clicked", async () => {
    const fn = vi.fn();
    render(<ReadingModeToggle mode="off" onToggle={fn} />);
    await userEvent.click(screen.getByRole("button", { name: /reading mode/i }));
    expect(fn).toHaveBeenCalledTimes(1);
  });
});
