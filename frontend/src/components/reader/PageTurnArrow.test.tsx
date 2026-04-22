import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { PageTurnArrow } from "./PageTurnArrow";

describe("PageTurnArrow", () => {
  it("renders left arrow with testid page-arrow-left and fires onClick", async () => {
    const fn = vi.fn();
    render(<PageTurnArrow direction="left" onClick={fn} />);
    const el = screen.getByTestId("page-arrow-left");
    await userEvent.click(el);
    expect(fn).toHaveBeenCalledTimes(1);
  });

  it("renders right arrow with testid page-arrow-right and fires onClick", async () => {
    const fn = vi.fn();
    render(<PageTurnArrow direction="right" onClick={fn} />);
    const el = screen.getByTestId("page-arrow-right");
    await userEvent.click(el);
    expect(fn).toHaveBeenCalledTimes(1);
  });

  it("sets aria-disabled=true when disabled", () => {
    render(<PageTurnArrow direction="left" onClick={() => {}} disabled />);
    const el = screen.getByTestId("page-arrow-left");
    expect(el.getAttribute("aria-disabled")).toBe("true");
  });

  it("does not fire onClick when disabled", async () => {
    const fn = vi.fn();
    render(<PageTurnArrow direction="right" onClick={fn} disabled />);
    await userEvent.click(screen.getByTestId("page-arrow-right"));
    expect(fn).not.toHaveBeenCalled();
  });
});
