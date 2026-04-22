import { describe, it, expect } from "vitest";
import { partitionForOverflow, getFolioFromAnchor } from "./overflow";
import type { AskCard, Card } from "./cards";

function ask(id: string, updatedAt: string, overrides: Partial<AskCard> = {}): Card {
  return {
    id,
    bookId: "b",
    anchor: "p1.s1",
    quote: "q",
    chapter: 1,
    kind: "ask",
    question: "Q",
    answer: "A",
    followups: [],
    createdAt: updatedAt,
    updatedAt,
    ...overrides,
  } as Card;
}

describe("partitionForOverflow", () => {
  it("with ≤2 cards returns all expanded and no collapsed", () => {
    const a = ask("a", "2026-04-22T00:00:00Z");
    const b = ask("b", "2026-04-22T00:01:00Z");
    const { collapsed, expanded } = partitionForOverflow([a, b]);
    expect(collapsed).toEqual([]);
    expect(expanded.map((c) => c.id).sort()).toEqual(["a", "b"]);
  });

  it("with 4 cards keeps the 2 newest expanded and the 2 oldest collapsed", () => {
    const cards = [
      ask("oldest", "2026-04-22T00:00:00Z"),
      ask("old", "2026-04-22T00:01:00Z"),
      ask("new", "2026-04-22T00:02:00Z"),
      ask("newest", "2026-04-22T00:03:00Z"),
    ];
    const { collapsed, expanded } = partitionForOverflow(cards);
    expect(expanded.map((c) => c.id)).toEqual(
      expect.arrayContaining(["new", "newest"]),
    );
    expect(expanded).toHaveLength(2);
    expect(collapsed.map((c) => c.id)).toEqual(
      expect.arrayContaining(["oldest", "old"]),
    );
    expect(collapsed).toHaveLength(2);
  });

  it("with 3 cards yields 1 collapsed + 2 expanded", () => {
    const cards = [
      ask("a", "2026-04-22T00:00:00Z"),
      ask("b", "2026-04-22T00:01:00Z"),
      ask("c", "2026-04-22T00:02:00Z"),
    ];
    const { collapsed, expanded } = partitionForOverflow(cards);
    expect(collapsed.map((c) => c.id)).toEqual(["a"]);
    expect(expanded).toHaveLength(2);
  });

  it("returns empty partitions for empty input", () => {
    expect(partitionForOverflow([])).toEqual({ collapsed: [], expanded: [] });
  });
});

describe("getFolioFromAnchor", () => {
  it("extracts the paragraph number from p{n}.s{m}", () => {
    expect(getFolioFromAnchor("p1.s2")).toBe(1);
    expect(getFolioFromAnchor("p12.s5")).toBe(12);
  });
});
