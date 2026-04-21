import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import { UserBubble } from "./UserBubble";

describe("UserBubble", () => {
  it("renders its text content", () => {
    render(<UserBubble text="Who is Marley?" />);
    expect(screen.getByText("Who is Marley?")).toBeInTheDocument();
  });

  it("renders as a right-aligned bubble (data-role='user')", () => {
    const { container } = render(<UserBubble text="Hello" />);
    const bubble = container.querySelector("[data-role='user']");
    expect(bubble).toBeTruthy();
  });

  it("does not render the page-at footer when pageAt is omitted", () => {
    render(<UserBubble text="no footer" />);
    expect(screen.queryByText(/asked at p\./i)).toBeNull();
  });

  it("renders the page-at footer when pageAt is provided", () => {
    render(<UserBubble text="with footer" pageAt={54} />);
    expect(screen.getByText(/asked at p\.\s*54/i)).toBeInTheDocument();
  });
});
