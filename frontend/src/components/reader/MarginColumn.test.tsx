import { describe, it, expect, beforeEach, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { MarginColumn } from "./MarginColumn";
import type { AskCard, Card } from "../../lib/reader/cards";

// Stub IntersectionObserver so useAnchorVisibility doesn't crash under JSDOM.
class IOStub {
  observe() {}
  unobserve() {}
  disconnect() {}
  takeRecords() {
    return [];
  }
}
beforeEach(() => {
  (globalThis as unknown as { IntersectionObserver: unknown }).IntersectionObserver =
    IOStub as unknown as typeof IntersectionObserver;
});

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

describe("MarginColumn — O2 overflow (R3)", () => {
  function mkAsk(id: string, anchor: string, updatedAt: string): AskCard {
    return {
      id,
      bookId: "b",
      anchor,
      quote: "q",
      chapter: 1,
      kind: "ask",
      question: `Q-${id}`,
      answer: `A-${id}`,
      followups: [],
      createdAt: updatedAt,
      updatedAt,
    };
  }

  it("renders a collapsed row + divider + 2 expanded when 3 cards are visible", () => {
    const cards: AskCard[] = [
      mkAsk("c1", "p1.s1", "2026-04-22T00:00:00Z"),
      mkAsk("c2", "p1.s2", "2026-04-22T00:01:00Z"),
      mkAsk("c3", "p1.s3", "2026-04-22T00:02:00Z"),
    ];
    render(
      <MarginColumn
        cards={cards}
        visibleSids={new Set(["p1.s1", "p1.s2", "p1.s3"])}
        focusedCardId={null}
        onBodyChange={() => {}}
        onBodyCommit={() => {}}
        leftSids={new Set(["p1.s1", "p1.s2", "p1.s3"])}
        rightSids={new Set()}
        leftFolio={1}
        rightFolio={2}
        bookRoot={null}
        onJump={() => {}}
        onFollowup={() => {}}
      />,
    );
    expect(screen.getAllByTestId("collapsed-card-row")).toHaveLength(1);
    expect(screen.getByTestId("latest-expanded-divider")).toBeInTheDocument();
    expect(document.querySelectorAll("[data-card-kind='ask']")).toHaveLength(2);
  });

  it("does not render divider when ≤2 visible cards", () => {
    const cards: AskCard[] = [
      mkAsk("c1", "p1.s1", "2026-04-22T00:00:00Z"),
      mkAsk("c2", "p1.s2", "2026-04-22T00:01:00Z"),
    ];
    render(
      <MarginColumn
        cards={cards}
        visibleSids={new Set(["p1.s1", "p1.s2"])}
        focusedCardId={null}
        onBodyChange={() => {}}
        onBodyCommit={() => {}}
        leftSids={new Set(["p1.s1", "p1.s2"])}
        rightSids={new Set()}
        leftFolio={1}
        rightFolio={2}
        bookRoot={null}
        onJump={() => {}}
        onFollowup={() => {}}
      />,
    );
    expect(screen.queryByTestId("latest-expanded-divider")).not.toBeInTheDocument();
    expect(screen.queryAllByTestId("collapsed-card-row")).toHaveLength(0);
  });

  it("renders AnchorConnector only when exactly 1 expanded card is visible", () => {
    const one: AskCard[] = [mkAsk("c1", "p1.s1", "2026-04-22T00:00:00Z")];
    const { rerender } = render(
      <MarginColumn
        cards={one}
        visibleSids={new Set(["p1.s1"])}
        focusedCardId={null}
        onBodyChange={() => {}}
        onBodyCommit={() => {}}
        leftSids={new Set(["p1.s1"])}
        rightSids={new Set()}
        leftFolio={1}
        rightFolio={2}
        bookRoot={document.body}
        onJump={() => {}}
        onFollowup={() => {}}
      />,
    );
    expect(screen.getByTestId("anchor-connector")).toBeInTheDocument();

    const two: AskCard[] = [
      mkAsk("c1", "p1.s1", "2026-04-22T00:00:00Z"),
      mkAsk("c2", "p1.s2", "2026-04-22T00:01:00Z"),
    ];
    rerender(
      <MarginColumn
        cards={two}
        visibleSids={new Set(["p1.s1", "p1.s2"])}
        focusedCardId={null}
        onBodyChange={() => {}}
        onBodyCommit={() => {}}
        leftSids={new Set(["p1.s1", "p1.s2"])}
        rightSids={new Set()}
        leftFolio={1}
        rightFolio={2}
        bookRoot={document.body}
        onJump={() => {}}
        onFollowup={() => {}}
      />,
    );
    expect(screen.queryByTestId("anchor-connector")).not.toBeInTheDocument();
  });

  it("renders aria-hidden and zero opacity when hidden prop is true", () => {
    render(
      <MarginColumn
        cards={[]}
        visibleSids={new Set()}
        focusedCardId={null}
        onBodyChange={() => {}}
        onBodyCommit={() => {}}
        hidden
      />,
    );
    const el = screen.getByTestId("margin-column");
    expect(el.getAttribute("aria-hidden")).toBe("true");
    expect(el.style.opacity).toBe("0");
    expect(el.style.transform).toContain("translateX(40px)");
    expect(el.style.pointerEvents).toBe("none");
  });

  it("does not set aria-hidden when hidden prop is false/absent", () => {
    render(
      <MarginColumn
        cards={[]}
        visibleSids={new Set()}
        focusedCardId={null}
        onBodyChange={() => {}}
        onBodyCommit={() => {}}
      />,
    );
    expect(
      screen.getByTestId("margin-column").getAttribute("aria-hidden"),
    ).not.toBe("true");
  });

  it("clicking a collapsed row promotes it and collapses the oldest-expanded", () => {
    const cards: AskCard[] = [
      mkAsk("oldest", "p1.s1", "2026-04-22T00:00:00Z"),
      mkAsk("middle", "p1.s2", "2026-04-22T00:01:00Z"),
      mkAsk("newest", "p1.s3", "2026-04-22T00:02:00Z"),
    ];
    render(
      <MarginColumn
        cards={cards}
        visibleSids={new Set(["p1.s1", "p1.s2", "p1.s3"])}
        focusedCardId={null}
        onBodyChange={() => {}}
        onBodyCommit={() => {}}
        leftSids={new Set(["p1.s1", "p1.s2", "p1.s3"])}
        rightSids={new Set()}
        leftFolio={1}
        rightFolio={2}
        bookRoot={null}
        onJump={() => {}}
        onFollowup={() => {}}
      />,
    );
    // Initially "oldest" is collapsed, "middle"+"newest" expanded.
    expect(
      document.querySelector('[data-card-id="oldest"]'),
    ).toBeNull();
    expect(
      document.querySelector('[data-card-id="middle"]'),
    ).not.toBeNull();
    // Click the collapsed row.
    fireEvent.click(screen.getByTestId("collapsed-card-row"));
    // Now "oldest" should be expanded (its card rendered).
    expect(
      document.querySelector('[data-card-id="oldest"]'),
    ).not.toBeNull();
    // And "middle" (previously oldest expanded by updatedAt) should be collapsed.
    expect(
      document.querySelector('[data-card-id="middle"]'),
    ).toBeNull();
  });
});
