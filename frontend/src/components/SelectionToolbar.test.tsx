import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { SelectionToolbar } from "./SelectionToolbar";

describe("SelectionToolbar", () => {
  it("renders Ask, Note, Highlight buttons and fires onAction", async () => {
    const onAction = vi.fn();
    render(
      <SelectionToolbar top={100} left={120} onAction={onAction} disabled={{}} />,
    );
    expect(screen.getByRole("button", { name: /Ask/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Note/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Highlight/i })).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: /Ask/i }));
    expect(onAction).toHaveBeenCalledWith("ask");
  });

  it("disables Ask when disabled.ask is true and does not fire onAction", async () => {
    const onAction = vi.fn();
    render(
      <SelectionToolbar
        top={0}
        left={0}
        onAction={onAction}
        disabled={{ ask: true }}
      />,
    );
    const ask = screen.getByRole("button", { name: /Ask/i });
    expect(ask).toBeDisabled();
    await userEvent.click(ask);
    expect(onAction).not.toHaveBeenCalled();
  });

  it("has role=toolbar positioned via inline top/left", () => {
    render(<SelectionToolbar top={77} left={33} onAction={() => {}} disabled={{}} />);
    const tb = screen.getByRole("toolbar");
    expect(tb.getAttribute("style")).toMatch(/top: 77px/);
    expect(tb.getAttribute("style")).toMatch(/left: 33px/);
  });
});
