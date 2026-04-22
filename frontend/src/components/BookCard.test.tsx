import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Routes, Route } from "react-router-dom";
import { BookCard } from "./BookCard";

describe("BookCard", () => {
  it("renders title, progress pill, and chapter-progress text", () => {
    render(
      <MemoryRouter>
        <BookCard
          book_id="christmas_carol_e6ddcd76"
          title="Christmas Carol"
          total_chapters={3}
          current_chapter={1}
        />
      </MemoryRouter>,
    );
    expect(screen.getAllByText("Christmas Carol").length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText("1")).toBeInTheDocument();
    expect(screen.getByText(/of\s*3/i)).toBeInTheDocument();
  });

  it("renders a BookCover with a stable mood", () => {
    const { container } = render(
      <MemoryRouter>
        <BookCard
          book_id="christmas_carol_e6ddcd76"
          title="Christmas Carol"
          total_chapters={3}
          current_chapter={1}
        />
      </MemoryRouter>,
    );
    expect(container.querySelector("[data-mood]")).toBeTruthy();
  });

  it("navigates to /books/:bookId/read on click", async () => {
    const user = userEvent.setup();
    render(
      <MemoryRouter initialEntries={["/"]}>
        <Routes>
          <Route
            path="/"
            element={
              <BookCard
                book_id="christmas_carol_e6ddcd76"
                title="Christmas Carol"
                total_chapters={3}
                current_chapter={1}
              />
            }
          />
          <Route path="/books/:bookId/read" element={<div>READING-LANDING</div>} />
        </Routes>
      </MemoryRouter>,
    );
    await user.click(screen.getByRole("button", { name: /christmas carol/i }));
    expect(await screen.findByText("READING-LANDING")).toBeInTheDocument();
  });
});
