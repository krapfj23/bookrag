import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import { Highlight } from "./Highlight";

describe("Highlight", () => {
  it("renders children inline as a <mark>/<span> with default styling", () => {
    render(<Highlight>Scrooge</Highlight>);
    expect(screen.getByText("Scrooge")).toBeInTheDocument();
  });

  it("accepts a variant prop", () => {
    const { container } = render(
      <Highlight variant="entity">Marley</Highlight>
    );
    expect(container.querySelector("[data-variant='entity']")).toBeTruthy();
  });
});
