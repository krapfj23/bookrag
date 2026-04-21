import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import { BookCard } from "./BookCard";

describe("BookCard", () => {
  it("renders title, progress pill, and chapter-progress text", () => {
    render(
      <BookCard
        book_id="christmas_carol_e6ddcd76"
        title="Christmas Carol"
        total_chapters={3}
        current_chapter={1}
      />
    );
    expect(screen.getByText("Christmas Carol")).toHaveLength;
    // the chapter-progress label "1 of 3"
    expect(screen.getByText("1")).toBeInTheDocument();
    expect(screen.getByText(/of\s*3/i)).toBeInTheDocument();
  });

  it("renders a BookCover with a stable mood", () => {
    const { container } = render(
      <BookCard
        book_id="christmas_carol_e6ddcd76"
        title="Christmas Carol"
        total_chapters={3}
        current_chapter={1}
      />
    );
    expect(container.querySelector("[data-mood]")).toBeTruthy();
  });
});
