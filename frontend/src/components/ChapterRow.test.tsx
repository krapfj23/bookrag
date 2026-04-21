import { render, screen } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import userEvent from "@testing-library/user-event";
import { ChapterRow } from "./ChapterRow";

describe("ChapterRow", () => {
  it("renders the zero-padded number and title", () => {
    render(<ChapterRow num={2} title="The Last of the Spirits" state="current" />);
    expect(screen.getByText("02")).toBeInTheDocument();
    expect(screen.getByText("The Last of the Spirits")).toBeInTheDocument();
  });

  it("marks state='current' with aria-current and accent styling", () => {
    render(<ChapterRow num={3} title="Now Reading" state="current" />);
    const row = screen.getByRole("button");
    expect(row).toHaveAttribute("aria-current", "true");
    expect(row).toHaveAttribute("data-state", "current");
  });

  it("marks state='read' with the check icon and non-current aria", () => {
    render(<ChapterRow num={1} title="Already Read" state="read" />);
    const row = screen.getByRole("button");
    expect(row).toHaveAttribute("data-state", "read");
    expect(row).not.toHaveAttribute("aria-current");
  });

  it("marks state='locked' as disabled with cursor not-allowed", () => {
    render(<ChapterRow num={4} title="Future" state="locked" />);
    const row = screen.getByRole("button");
    expect(row).toHaveAttribute("data-state", "locked");
    expect(row).toHaveAttribute("aria-disabled", "true");
    expect(row).toHaveStyle({ cursor: "not-allowed" });
  });

  it("calls onClick when state is 'read' or 'current'", async () => {
    const user = userEvent.setup();
    const onClick = vi.fn();
    render(<ChapterRow num={1} title="Go" state="read" onClick={onClick} />);
    await user.click(screen.getByRole("button"));
    expect(onClick).toHaveBeenCalledTimes(1);
  });

  it("does NOT call onClick when state is 'locked'", async () => {
    const user = userEvent.setup();
    const onClick = vi.fn();
    render(<ChapterRow num={5} title="No" state="locked" onClick={onClick} />);
    await user.click(screen.getByRole("button"));
    expect(onClick).not.toHaveBeenCalled();
  });
});
