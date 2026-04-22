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
