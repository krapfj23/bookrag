import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { MarginColumn } from "./MarginColumn";
import type { Card } from "../../lib/reader/cards";

const ask: Card = {
  id: "a1",
  bookId: "b",
  anchor: "p1.s1",
  quote: "hello world",
  chapter: 1,
  kind: "ask",
  question: "what?",
  answer: "streaming...",
  followups: [],
  createdAt: "",
  updatedAt: "",
};
const note: Card = {
  id: "n1",
  bookId: "b",
  anchor: "p1.s2",
  quote: "nt",
  chapter: 1,
  kind: "note",
  body: "my thought",
  createdAt: "",
  updatedAt: "",
};

describe("MarginColumn", () => {
  it("renders S1 empty-state when no cards match visible anchors", () => {
    render(
      <MarginColumn
        cards={[]}
        visibleSids={new Set(["p1.s1"])}
        focusedCardId={null}
        onBodyChange={() => {}}
        onBodyCommit={() => {}}
      />,
    );
    expect(
      screen.getByRole("heading", { name: /Ask about what you're reading/i }),
    ).toBeInTheDocument();
  });

  it("filters cards by visibleSids", () => {
    render(
      <MarginColumn
        cards={[ask, note]}
        visibleSids={new Set(["p1.s1"])}
        focusedCardId={null}
        onBodyChange={() => {}}
        onBodyCommit={() => {}}
      />,
    );
    expect(screen.getByText(/streaming/)).toBeInTheDocument();
    expect(screen.queryByText(/my thought/)).not.toBeInTheDocument();
  });

  it("renders card with data-card-id for anchor lookup", () => {
    render(
      <MarginColumn
        cards={[ask]}
        visibleSids={new Set(["p1.s1"])}
        focusedCardId={null}
        onBodyChange={() => {}}
        onBodyCommit={() => {}}
      />,
    );
    expect(document.querySelector('[data-card-id="a1"]')).not.toBeNull();
  });

  it("applies focus-flash class when focusedCardId matches", () => {
    render(
      <MarginColumn
        cards={[ask]}
        visibleSids={new Set(["p1.s1"])}
        focusedCardId="a1"
        onBodyChange={() => {}}
        onBodyCommit={() => {}}
      />,
    );
    const el = document.querySelector('[data-card-id="a1"]') as HTMLElement;
    expect(el.className).toMatch(/rr-card-flash/);
  });
});
