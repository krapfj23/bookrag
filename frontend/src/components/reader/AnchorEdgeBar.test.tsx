import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { AnchorEdgeBar } from "./AnchorEdgeBar";
import { JumpToAnchorCTA } from "./JumpToAnchorCTA";
import { AskCard } from "./AskCard";
import { NoteCard } from "./NoteCard";
import type {
  AskCard as AskCardT,
  NoteCard as NoteCardT,
} from "../../lib/reader/cards";

describe("AnchorEdgeBar", () => {
  it("renders an absolutely positioned bar at the given top with width 3", () => {
    render(<AnchorEdgeBar top={120} color="var(--accent)" />);
    const bar = screen.getByTestId("anchor-edge-bar");
    const style = bar.getAttribute("style") ?? "";
    expect(style).toMatch(/position:\s*absolute/);
    expect(style).toMatch(/top:\s*120px/);
    expect(style).toMatch(/width:\s*3px/);
    expect(style).toMatch(/var\(--accent\)/);
  });
});

describe("JumpToAnchorCTA", () => {
  it("fires onJump when clicked", () => {
    const onJump = vi.fn();
    render(<JumpToAnchorCTA onJump={onJump} />);
    const btn = screen.getByTestId("jump-to-anchor-cta");
    fireEvent.click(btn);
    expect(onJump).toHaveBeenCalledTimes(1);
  });

  it("renders with 'Jump to anchor on this page' label text", () => {
    render(<JumpToAnchorCTA onJump={() => {}} />);
    expect(
      screen.getByText(/Jump to anchor on this page/i),
    ).toBeInTheDocument();
  });
});

describe("AskCard off-screen prefix (S6)", () => {
  const base: AskCardT = {
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
  };

  it("prefixes header with ↑ SCROLL UP · when offscreen.direction is up", () => {
    render(
      <AskCard
        card={base}
        flash={false}
        offscreen={{ direction: "up" }}
      />,
    );
    expect(screen.getByText(/↑ SCROLL UP ·/)).toBeInTheDocument();
  });

  it("prefixes header with ↓ SCROLL DOWN · when offscreen.direction is down", () => {
    render(
      <AskCard
        card={base}
        flash={false}
        offscreen={{ direction: "down" }}
      />,
    );
    expect(screen.getByText(/↓ SCROLL DOWN ·/)).toBeInTheDocument();
  });

  it("renders the jump CTA below the card when offscreen + onJump provided", () => {
    const onJump = vi.fn();
    render(
      <AskCard
        card={base}
        flash={false}
        offscreen={{ direction: "up" }}
        onJump={onJump}
      />,
    );
    fireEvent.click(screen.getByTestId("jump-to-anchor-cta"));
    expect(onJump).toHaveBeenCalledTimes(1);
  });
});

describe("NoteCard off-screen prefix (S6)", () => {
  const note: NoteCardT = {
    id: "n1",
    bookId: "b",
    anchor: "p1.s2",
    quote: "q",
    chapter: 1,
    kind: "note",
    body: "hi",
    createdAt: "",
    updatedAt: "",
  };

  it("prefixes header with ↑ SCROLL UP · when offscreen.direction is up", () => {
    render(
      <NoteCard
        card={note}
        flash={false}
        autoFocus={false}
        onBodyChange={() => {}}
        onBodyCommit={() => {}}
        offscreen={{ direction: "up" }}
      />,
    );
    expect(screen.getByText(/↑ SCROLL UP ·/)).toBeInTheDocument();
  });
});
