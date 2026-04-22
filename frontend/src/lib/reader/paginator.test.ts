/**
 * @vitest-environment jsdom
 */
import { describe, it, expect } from "vitest";
import { paginate, type Spread } from "./paginator";
import type { AnchoredParagraph } from "../api";

function para(idx: number, n: number): AnchoredParagraph {
  return {
    paragraph_idx: idx,
    sentences: Array.from({ length: n }, (_, i) => ({
      sid: `p${idx}.s${i + 1}`,
      text: `Sentence ${i + 1} of paragraph ${idx}.`,
    })),
  };
}

describe("paginate", () => {
  it("returns at least one spread and never splits a sentence", () => {
    const paragraphs: AnchoredParagraph[] = [
      para(1, 3),
      para(2, 2),
      para(3, 4),
    ];
    const spreads: Spread[] = paginate(paragraphs, {
      pageWidth: 360,
      pageHeight: 520,
      paddingPx: 48,
      fontPx: 15,
      lineHeight: 1.72,
    });
    expect(spreads.length).toBeGreaterThanOrEqual(1);
    const seen = new Set<string>();
    for (const sp of spreads) {
      for (const page of [sp.left, sp.right]) {
        for (const p of page) {
          for (const s of p.sentences) {
            expect(seen.has(s.sid)).toBe(false);
            seen.add(s.sid);
          }
        }
      }
    }
    // Every sentence appears exactly once.
    expect(seen.size).toBe(3 + 2 + 4);
  });

  it("produces spreads with last visible sid available", () => {
    const spreads = paginate([para(1, 2)], {
      pageWidth: 360,
      pageHeight: 520,
      paddingPx: 48,
      fontPx: 15,
      lineHeight: 1.72,
    });
    expect(spreads[0].lastSid).toBe("p1.s2");
  });
});
