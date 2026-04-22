/**
 * T12 — Chat-open animation: AskCard renders with rr-card-enter className on mount.
 */
import { describe, it, expect } from "vitest";
import { render } from "@testing-library/react";
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

describe("AskCard T12 — enter animation class", () => {
  it("newly mounted non-loading card has rr-card-enter in className", () => {
    const { container } = render(
      <AskCard card={makeCard()} flash={false} />
    );
    const article = container.querySelector("article[data-card-kind='ask']");
    expect(article).not.toBeNull();
    expect(article!.className).toContain("rr-card-enter");
  });
});
