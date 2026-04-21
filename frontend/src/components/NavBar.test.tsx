import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import { NavBar } from "./NavBar";

describe("NavBar", () => {
  it("renders the three tabs and the wordmark", () => {
    render(<NavBar active="library" />);
    expect(screen.getByText("Library")).toBeInTheDocument();
    expect(screen.getByText("Reading")).toBeInTheDocument();
    expect(screen.getByText("Upload")).toBeInTheDocument();
    expect(screen.getByText(/book/i)).toBeInTheDocument();
  });

  it("marks the active tab with aria-current and a data attribute", () => {
    render(<NavBar active="library" />);
    const active = screen.getByText("Library");
    expect(active).toHaveAttribute("aria-current", "page");
    expect(active).toHaveAttribute("data-active", "true");
  });

  it("non-active tabs are inert but do not throw when clicked", async () => {
    const { default: userEvent } = await import("@testing-library/user-event");
    const user = userEvent.setup();
    render(<NavBar active="library" />);
    await user.click(screen.getByText("Reading"));
    await user.click(screen.getByText("Upload"));
    expect(screen.getByText("Library")).toHaveAttribute("aria-current", "page");
  });
});
