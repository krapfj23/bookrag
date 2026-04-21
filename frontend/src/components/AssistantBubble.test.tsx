import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import { AssistantBubble, type AssistantSource } from "./AssistantBubble";

describe("AssistantBubble", () => {
  it("renders its text content", () => {
    render(<AssistantBubble text="Marley is Scrooge's dead partner." />);
    expect(
      screen.getByText(/marley is scrooge's dead partner/i)
    ).toBeInTheDocument();
  });

  it("renders with data-role='assistant' for the transcript", () => {
    const { container } = render(<AssistantBubble text="x" />);
    expect(container.querySelector("[data-role='assistant']")).toBeTruthy();
  });

  it("renders the avatar disc", () => {
    render(<AssistantBubble text="x" />);
    expect(screen.getByText("r")).toBeInTheDocument();
  });

  it("does not render sources when sources is undefined", () => {
    const { container } = render(<AssistantBubble text="no sources" />);
    expect(container.querySelector("[data-source-index]")).toBeNull();
  });

  it("does not render sources when sources is empty", () => {
    const { container } = render(<AssistantBubble text="empty" sources={[]} />);
    expect(container.querySelector("[data-source-index]")).toBeNull();
  });

  it("renders up to 5 sources, truncated to 200 chars + ellipsis", () => {
    const longText = "x".repeat(400);
    const sources: AssistantSource[] = [
      { text: "Short one.", chapter: 1 },
      { text: "Second.", chapter: 2 },
      { text: "Third.", chapter: 3 },
      { text: "Fourth.", chapter: 4 },
      { text: "Fifth.", chapter: 5 },
      { text: "Sixth — should be dropped.", chapter: 6 },
      { text: longText, chapter: 7 }, // should not appear (past 5)
    ];
    const { container } = render(
      <AssistantBubble text="answer" sources={sources} />
    );
    const rendered = container.querySelectorAll("[data-source-index]");
    expect(rendered.length).toBe(5);
    expect(screen.queryByText(/sixth/i)).toBeNull();
  });

  it("truncates individual source text longer than 200 chars", () => {
    const longText = "A".repeat(250);
    render(
      <AssistantBubble
        text="answer"
        sources={[{ text: longText, chapter: 1 }]}
      />
    );
    // The rendered text should contain the ellipsis and be shorter than 250.
    const el = screen.getByText(/A{10,}…/);
    expect(el.textContent!.length).toBeLessThan(250);
    expect(el.textContent!.endsWith("…")).toBe(true);
  });

  it("renders Ch. {n} label per source", () => {
    render(
      <AssistantBubble
        text="answer"
        sources={[
          { text: "from ch 1", chapter: 1 },
          { text: "from ch 3", chapter: 3 },
        ]}
      />
    );
    expect(screen.getByText("Ch. 1")).toBeInTheDocument();
    expect(screen.getByText("Ch. 3")).toBeInTheDocument();
  });

  it("when thinking=true, renders the blinking cursor", () => {
    const { container } = render(
      <AssistantBubble text="Thinking…" thinking />
    );
    expect(container.querySelector(".br-cursor")).toBeTruthy();
  });

  it("when thinking=false (default), omits the cursor", () => {
    const { container } = render(<AssistantBubble text="done" />);
    expect(container.querySelector(".br-cursor")).toBeNull();
  });
});
