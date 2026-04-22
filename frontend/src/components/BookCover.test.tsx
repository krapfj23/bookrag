import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import { BookCover } from "./BookCover";

describe("BookCover", () => {
  it("renders the title", () => {
    render(<BookCover book_id="christmas_carol_e6ddcd76" title="Christmas Carol" />);
    expect(screen.getByText("Christmas Carol")).toBeInTheDocument();
  });

  it("derives a stable mood attribute from book_id", () => {
    const { container, rerender } = render(
      <BookCover book_id="abc_12345678" title="X" />,
    );
    const first = container.querySelector("[data-mood]")?.getAttribute("data-mood");
    rerender(<BookCover book_id="abc_12345678" title="X" />);
    const second = container.querySelector("[data-mood]")?.getAttribute("data-mood");
    expect(first).toBe(second);
    expect(first).toMatch(/^(sage|amber|slate|rose|charcoal|paper)$/);
  });
});
