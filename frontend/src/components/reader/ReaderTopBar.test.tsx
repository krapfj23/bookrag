/**
 * T1 — ReaderTopBar: correct structure, Ask pill uses --accent,
 * no global nav links (Library/Upload) in the reader top bar.
 */
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { ReaderTopBar } from "./ReaderTopBar";

function renderBar(props = {}) {
  return render(
    <MemoryRouter>
      <ReaderTopBar title="A Christmas Carol" mode="off" onToggleMode={() => {}} {...props} />
    </MemoryRouter>
  );
}

describe("ReaderTopBar T1 — structure", () => {
  it("renders header with data-testid reader-topbar", () => {
    renderBar();
    expect(screen.getByTestId("reader-topbar")).toBeInTheDocument();
  });

  it("has a Back to library button", () => {
    renderBar();
    expect(screen.getByRole("button", { name: /back to library/i })).toBeInTheDocument();
  });

  it("has an Ask button", () => {
    renderBar();
    expect(screen.getByRole("button", { name: /ask/i })).toBeInTheDocument();
  });

  it("Ask button uses var(--accent) background in style", () => {
    renderBar();
    const ask = screen.getByRole("button", { name: /ask/i });
    const style = ask.getAttribute("style") ?? "";
    expect(style).toContain("var(--accent)");
  });

  it("Ask button has border-radius 999px", () => {
    renderBar();
    const ask = screen.getByRole("button", { name: /ask/i });
    const style = ask.getAttribute("style") ?? "";
    expect(style).toMatch(/border-radius:\s*999px/);
  });

  it("does not contain a link to /upload", () => {
    renderBar();
    const uploadLinks = screen.queryAllByRole("link", { name: /upload/i });
    expect(uploadLinks).toHaveLength(0);
  });
});
