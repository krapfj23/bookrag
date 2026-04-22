/**
 * @vitest-environment jsdom
 */
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { BookSpread } from "./BookSpread";
import type { Page } from "../../lib/reader/paginator";

const leftPage: Page = [
  {
    paragraph_idx: 1,
    sentences: [
      { sid: "p1.s1", text: "Alpha." },
      { sid: "p1.s2", text: "Bravo." },
    ],
  },
];
const rightPage: Page = [
  {
    paragraph_idx: 2,
    sentences: [{ sid: "p2.s1", text: "Charlie." }],
  },
];

describe("BookSpread — T1 fixed dimensions", () => {
  it("has stable outer width and min-height across content sizes", () => {
    const thin = {
      left: [{ paragraph_idx: 0, sentences: [{ sid: "p1.s1", text: "A." }] }],
      right: [] as { paragraph_idx: number; sentences: { sid: string; text: string }[] }[],
    };
    const fat = {
      left: Array.from({ length: 6 }, (_, i) => ({
        paragraph_idx: i,
        sentences: [{ sid: `p${i + 1}.s1`, text: "Long paragraph ".repeat(12) }],
      })),
      right: Array.from({ length: 6 }, (_, i) => ({
        paragraph_idx: i + 6,
        sentences: [{ sid: `p${i + 7}.s1`, text: "Long paragraph ".repeat(12) }],
      })),
    };
    const { container, rerender } = render(
      <BookSpread
        chapterNum={1}
        chapterTitle="Chapter 1"
        totalChapters={3}
        left={thin.left as Page}
        right={thin.right as Page}
        folioLeft={1}
        folioRight={2}
        cursor="p1.s1"
      />,
    );
    const thinBox = container.querySelector(".rr-book") as HTMLElement;
    const thinStyle = thinBox.getAttribute("style") || "";
    expect(thinStyle).toMatch(/width:\s*\d+px/);
    expect(thinStyle).toMatch(/min-height:\s*\d+px/);

    rerender(
      <BookSpread
        chapterNum={1}
        chapterTitle="Chapter 1"
        totalChapters={3}
        left={fat.left as Page}
        right={fat.right as Page}
        folioLeft={1}
        folioRight={2}
        cursor="p1.s1"
      />,
    );
    const fatBox = container.querySelector(".rr-book") as HTMLElement;
    expect(fatBox.getAttribute("style")).toContain(
      thinStyle.match(/width:\s*\d+px/)![0],
    );
  });
});

describe("BookSpread", () => {
  it("renders both pages with sentence data-sid", () => {
    render(
      <BookSpread
        chapterNum={1}
        chapterTitle="Marley's Ghost"
        totalChapters={5}
        left={leftPage}
        right={rightPage}
        folioLeft={1}
        folioRight={2}
        cursor="p1.s1"
      />,
    );
    expect(document.querySelector('[data-sid="p1.s1"]')).not.toBeNull();
    expect(document.querySelector('[data-sid="p1.s2"]')).not.toBeNull();
    expect(document.querySelector('[data-sid="p2.s1"]')).not.toBeNull();
    expect(screen.getByText(/Marley's Ghost/)).toBeInTheDocument();
  });

  it("marks first paragraph of the chapter with drop cap on first spread", () => {
    render(
      <BookSpread
        chapterNum={1}
        chapterTitle="T"
        totalChapters={1}
        left={leftPage}
        right={[]}
        folioLeft={1}
        folioRight={2}
        cursor="p1.s1"
        isFirstSpread={true}
      />,
    );
    expect(document.querySelector(".rr-dropcap")).not.toBeNull();
  });
});
