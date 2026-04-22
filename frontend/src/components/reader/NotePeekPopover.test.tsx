import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { NotePeekPopover } from "./NotePeekPopover";

describe("NotePeekPopover", () => {
  it("renders note-peek with body when visible", () => {
    render(<NotePeekPopover visible={true} body="my note body" x={120} y={300} />);
    const el = screen.getByTestId("note-peek");
    expect(el).toBeInTheDocument();
    expect(el.textContent ?? "").toContain("my note body");
  });

  it("does not render when not visible", () => {
    render(<NotePeekPopover visible={false} body="hidden" x={0} y={0} />);
    expect(screen.queryByTestId("note-peek")).not.toBeInTheDocument();
  });
});
