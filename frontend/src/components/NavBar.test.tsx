import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import { MemoryRouter } from "react-router-dom";
import { NavBar } from "./NavBar";

function renderAt(path: string) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <NavBar />
    </MemoryRouter>
  );
}

describe("NavBar", () => {
  it("renders the three tabs and the wordmark", () => {
    renderAt("/");
    expect(screen.getByText("Library")).toBeInTheDocument();
    expect(screen.getByText("Reading")).toBeInTheDocument();
    expect(screen.getByText("Upload")).toBeInTheDocument();
    expect(screen.getByText(/book/i)).toBeInTheDocument();
  });

  it("marks Library active when the route is /", () => {
    renderAt("/");
    const active = screen.getByText("Library");
    expect(active).toHaveAttribute("aria-current", "page");
    expect(active).toHaveAttribute("data-active", "true");
    expect(screen.getByText("Upload")).toHaveAttribute("data-active", "false");
  });

  it("marks Upload active when the route is /upload", () => {
    renderAt("/upload");
    expect(screen.getByText("Upload")).toHaveAttribute("aria-current", "page");
    expect(screen.getByText("Library")).toHaveAttribute("data-active", "false");
  });

  it("Reading stays inert — clicking it does not throw and does not change the active tab", async () => {
    const { default: userEvent } = await import("@testing-library/user-event");
    const user = userEvent.setup();
    renderAt("/");
    await user.click(screen.getByText("Reading"));
    expect(screen.getByText("Library")).toHaveAttribute("aria-current", "page");
  });

  it("Library and Upload are real links with href attributes", () => {
    renderAt("/");
    expect(screen.getByText("Library").closest("a")).toHaveAttribute("href", "/");
    expect(screen.getByText("Upload").closest("a")).toHaveAttribute("href", "/upload");
  });

  it("marks Reading active on /books/:bookId/read/:n", () => {
    renderAt("/books/christmas_carol_e6ddcd76/read/2");
    expect(screen.getByText("Reading")).toHaveAttribute("data-active", "true");
    expect(screen.getByText("Library")).toHaveAttribute("data-active", "false");
    expect(screen.getByText("Upload")).toHaveAttribute("data-active", "false");
  });
});
