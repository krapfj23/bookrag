import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { CollapsedCardRow } from "./CollapsedCardRow";
import { LatestExpandedDivider } from "./LatestExpandedDivider";
import type { AskCard, NoteCard } from "../../lib/reader/cards";

const ask: AskCard = {
  id: "a1",
  bookId: "b",
  anchor: "p3.s2",
  quote: "q",
  chapter: 1,
  kind: "ask",
  question: "What is freedom?",
  answer: "",
  followups: [],
  createdAt: "",
  updatedAt: "",
};

const note: NoteCard = {
  id: "n1",
  bookId: "b",
  anchor: "p4.s1",
  quote: "q",
  chapter: 1,
  kind: "note",
  body: "first line of the note\nsecond",
  createdAt: "",
  updatedAt: "",
};

describe("CollapsedCardRow", () => {
  it("renders an ask card with p.{n} · {italic question} · › text", () => {
    render(<CollapsedCardRow card={ask} onExpand={() => {}} />);
    const row = screen.getByTestId("collapsed-card-row");
    const text = row.textContent ?? "";
    expect(text).toMatch(/p\.3/);
    expect(text).toMatch(/What is freedom\?/);
    expect(text).toMatch(/›/);
  });

  it("applies border-left 3px var(--accent) styling for ask kind", () => {
    render(<CollapsedCardRow card={ask} onExpand={() => {}} />);
    const row = screen.getByTestId("collapsed-card-row");
    const style = row.getAttribute("style") ?? "";
    expect(style).toMatch(/border-left:\s*3px/);
    expect(style).toMatch(/var\(--accent\)/);
  });

  it("uses note-orange left border for note kind", () => {
    render(<CollapsedCardRow card={note} onExpand={() => {}} />);
    const row = screen.getByTestId("collapsed-card-row");
    const style = row.getAttribute("style") ?? "";
    expect(style).toMatch(/border-left:\s*3px/);
    // Note border is orange (oklch); should NOT be var(--accent).
    expect(style).not.toMatch(/var\(--accent\)/);
  });

  it("renders the first line of a note body when kind is note", () => {
    render(<CollapsedCardRow card={note} onExpand={() => {}} />);
    const row = screen.getByTestId("collapsed-card-row");
    const text = row.textContent ?? "";
    expect(text).toMatch(/first line of the note/);
    expect(text).not.toMatch(/second/);
  });

  it("calls onExpand(card.id) on click", () => {
    const onExpand = vi.fn();
    render(<CollapsedCardRow card={ask} onExpand={onExpand} />);
    fireEvent.click(screen.getByTestId("collapsed-card-row"));
    expect(onExpand).toHaveBeenCalledWith("a1");
  });
});

describe("LatestExpandedDivider", () => {
  it("renders the divider with the 'Latest · expanded' label", () => {
    render(<LatestExpandedDivider />);
    const divider = screen.getByTestId("latest-expanded-divider");
    expect(divider.textContent ?? "").toMatch(/Latest · expanded/i);
  });
});
