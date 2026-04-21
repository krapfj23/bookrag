import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import { LockState } from "./LockState";

describe("LockState", () => {
  it("renders spoilerSafe pill with label", () => {
    render(<LockState variant="spoilerSafe" label="safe through ch. 3" />);
    expect(screen.getByText(/safe through ch\. 3/i)).toBeInTheDocument();
  });

  it("spoilerSafe is a small pill (role status)", () => {
    render(<LockState variant="spoilerSafe" label="x" />);
    expect(screen.getByRole("status")).toBeInTheDocument();
  });

  it("renders chapterLock full panel with title and padlock", () => {
    render(
      <LockState
        variant="chapterLock"
        chapterTitle="The Last of the Spirits"
        chapterNum={4}
      />
    );
    expect(screen.getByText("The Last of the Spirits")).toBeInTheDocument();
    expect(screen.getByText(/locked/i)).toBeInTheDocument();
  });
});
