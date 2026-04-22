import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { AskCard } from "./AskCard";
import type { AskCard as AskCardT } from "../../lib/reader/cards";

function makeCard(overrides: Partial<AskCardT> = {}): AskCardT {
  return {
    id: "a1",
    bookId: "b",
    anchor: "p1.s1",
    quote: "quote",
    chapter: 1,
    kind: "ask",
    question: "what?",
    answer: "an answer",
    followups: [],
    createdAt: "",
    updatedAt: "",
    ...overrides,
  };
}

describe("AskCard S3 (loading / streaming)", () => {
  it("renders SkeletonAskCard when card.loading is true", () => {
    render(
      <AskCard
        card={makeCard({ loading: true, answer: "" } as Partial<AskCardT>)}
        flash={false}
      />,
    );
    expect(screen.getByTestId("skeleton-ask-card")).toBeInTheDocument();
    expect(screen.queryByTestId("ask-answer")).not.toBeInTheDocument();
  });

  it("renders the answer and the BlinkingCursor when card.streaming is true", () => {
    render(
      <AskCard
        card={makeCard({ streaming: true, answer: "hi" } as Partial<AskCardT>)}
        flash={false}
      />,
    );
    expect(screen.getByTestId("ask-answer")).toHaveTextContent("hi");
    expect(screen.getByTestId("blinking-cursor")).toBeInTheDocument();
  });

  it("omits the BlinkingCursor when streaming is false", () => {
    render(
      <AskCard card={makeCard({ answer: "done" })} flash={false} />,
    );
    expect(screen.queryByTestId("blinking-cursor")).not.toBeInTheDocument();
  });
});

describe("AskCard S4 (long-answer scroll + fade)", () => {
  let origDescriptor: PropertyDescriptor | undefined;

  beforeEach(() => {
    origDescriptor = Object.getOwnPropertyDescriptor(
      HTMLElement.prototype,
      "scrollHeight",
    );
    Object.defineProperty(HTMLElement.prototype, "scrollHeight", {
      configurable: true,
      get() {
        // Long enough to exceed the 220px threshold.
        return 400;
      },
    });
  });

  afterEach(() => {
    if (origDescriptor) {
      Object.defineProperty(HTMLElement.prototype, "scrollHeight", origDescriptor);
    }
    vi.restoreAllMocks();
  });

  it("constrains the answer container with overflow:auto when answer exceeds 220px", () => {
    render(
      <AskCard
        card={makeCard({
          answer: "word ".repeat(400),
        })}
        flash={false}
      />,
    );
    const answer = screen.getByTestId("ask-answer");
    const style = answer.getAttribute("style") ?? "";
    expect(style).toMatch(/overflow(-y)?:\s*auto/);
    expect(style).toMatch(/max-height:\s*220px/);
  });

  it("renders the ask-answer-fade overlay when answer is long", () => {
    render(
      <AskCard
        card={makeCard({
          answer: "word ".repeat(400),
        })}
        flash={false}
      />,
    );
    expect(screen.getByTestId("ask-answer-fade")).toBeInTheDocument();
  });
});

describe("AskCard short-answer path (no fade)", () => {
  let origDescriptor: PropertyDescriptor | undefined;
  beforeEach(() => {
    origDescriptor = Object.getOwnPropertyDescriptor(
      HTMLElement.prototype,
      "scrollHeight",
    );
    Object.defineProperty(HTMLElement.prototype, "scrollHeight", {
      configurable: true,
      get() {
        return 80;
      },
    });
  });
  afterEach(() => {
    if (origDescriptor) {
      Object.defineProperty(HTMLElement.prototype, "scrollHeight", origDescriptor);
    }
  });

  it("does not render the ask-answer-fade overlay when answer is short", () => {
    render(<AskCard card={makeCard({ answer: "short" })} flash={false} />);
    expect(screen.queryByTestId("ask-answer-fade")).not.toBeInTheDocument();
  });
});
