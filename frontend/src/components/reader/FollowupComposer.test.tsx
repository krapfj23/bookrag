import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { FollowupComposer } from "./FollowupComposer";
import { AskCard } from "./AskCard";
import type { AskCard as AskCardT } from "../../lib/reader/cards";

function makeCard(overrides: Partial<AskCardT> = {}): AskCardT {
  return {
    id: "a1",
    bookId: "b",
    anchor: "p1.s1",
    quote: "q",
    chapter: 1,
    kind: "ask",
    question: "Q?",
    answer: "A",
    followups: [],
    createdAt: "",
    updatedAt: "",
    ...overrides,
  };
}

describe("FollowupComposer", () => {
  it("renders a placeholder input", () => {
    render(<FollowupComposer onSubmit={() => {}} />);
    const input = screen.getByPlaceholderText(/Ask a follow-up/i);
    expect(input).toBeInTheDocument();
  });

  it("submits on Enter and clears the input", () => {
    const onSubmit = vi.fn();
    render(<FollowupComposer onSubmit={onSubmit} />);
    const input = screen.getByPlaceholderText(
      /Ask a follow-up/i,
    ) as HTMLInputElement;
    fireEvent.change(input, { target: { value: "why?" } });
    fireEvent.keyDown(input, { key: "Enter" });
    expect(onSubmit).toHaveBeenCalledWith("why?");
    expect(input.value).toBe("");
  });

  it("does not submit empty input on Enter", () => {
    const onSubmit = vi.fn();
    render(<FollowupComposer onSubmit={onSubmit} />);
    const input = screen.getByPlaceholderText(/Ask a follow-up/i);
    fireEvent.keyDown(input, { key: "Enter" });
    expect(onSubmit).not.toHaveBeenCalled();
  });
});

describe("AskCard followup rendering (S5)", () => {
  it("renders each followup in a dashed-bordered thread block", () => {
    render(
      <AskCard
        card={makeCard({
          followups: [
            { question: "why?", answer: "because" },
            { question: "how?", answer: "like this" },
          ],
        })}
        flash={false}
      />,
    );
    const blocks = screen.getAllByTestId("followup");
    expect(blocks).toHaveLength(2);
    for (const block of blocks) {
      const style = block.getAttribute("style") ?? "";
      expect(style).toMatch(/border-left/);
      expect(style).toMatch(/dashed/);
    }
    // FOLLOW-UP header label appears per block.
    const headers = screen.getAllByText(/FOLLOW-UP/);
    expect(headers.length).toBeGreaterThanOrEqual(2);
  });

  it("appends a blinking cursor after the last followup when followupLoading is true", () => {
    render(
      <AskCard
        card={makeCard({
          followups: [{ question: "why?", answer: "partial" }],
          followupLoading: true,
        } as Partial<AskCardT>)}
        flash={false}
      />,
    );
    expect(screen.getByTestId("blinking-cursor")).toBeInTheDocument();
  });

  it("renders the follow-up composer below the answer when not loading", () => {
    render(<AskCard card={makeCard()} flash={false} />);
    expect(
      screen.getByPlaceholderText(/Ask a follow-up/i),
    ).toBeInTheDocument();
  });
});
