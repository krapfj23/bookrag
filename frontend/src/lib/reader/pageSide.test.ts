import { describe, it, expect } from "vitest";
import { computeCrossPage } from "./pageSide";

describe("computeCrossPage", () => {
  const leftSids = new Set(["p1.s1", "p1.s2"]);
  const rightSids = new Set(["p2.s1", "p2.s2"]);

  it("returns {direction:'left', folio:leftFolio} for anchors on the left page", () => {
    const r = computeCrossPage({
      sid: "p1.s2",
      leftSids,
      rightSids,
      leftFolio: 1,
      rightFolio: 2,
    });
    expect(r).toEqual({ direction: "left", folio: 1 });
  });

  it("returns null for anchors on the right page (margin column sits on right)", () => {
    const r = computeCrossPage({
      sid: "p2.s1",
      leftSids,
      rightSids,
      leftFolio: 1,
      rightFolio: 2,
    });
    expect(r).toBeNull();
  });

  it("returns null when sid is on neither page", () => {
    const r = computeCrossPage({
      sid: "p9.s9",
      leftSids,
      rightSids,
      leftFolio: 1,
      rightFolio: 2,
    });
    expect(r).toBeNull();
  });
});

describe("AskCard cross-page prefix (S7)", () => {
  it("prepends ← FROM p. {n} · when crossPage prop provided", async () => {
    const { render, screen } = await import("@testing-library/react");
    const { AskCard } = await import("../../components/reader/AskCard");
    const card = {
      id: "a1",
      bookId: "b",
      anchor: "p1.s2",
      quote: "q",
      chapter: 1,
      kind: "ask" as const,
      question: "Q?",
      answer: "A",
      followups: [],
      createdAt: "",
      updatedAt: "",
    };
    render(
      <AskCard
        card={card}
        flash={false}
        crossPage={{ direction: "left", folio: 1 }}
      />,
    );
    expect(screen.getByText(/← FROM p\. 1 ·/)).toBeInTheDocument();
  });
});
