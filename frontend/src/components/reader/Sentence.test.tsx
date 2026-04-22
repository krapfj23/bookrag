import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { Sentence } from "./Sentence";
import { Paragraph } from "./Paragraph";

describe("Sentence", () => {
  it("emits data-sid and text", () => {
    render(<Sentence sid="p1.s2" text="Hello." fogged={false} />);
    const el = screen.getByText("Hello.");
    expect(el.getAttribute("data-sid")).toBe("p1.s2");
  });

  it("applies fog styling when fogged", () => {
    render(<Sentence sid="p1.s2" text="Hello." fogged={true} />);
    const el = screen.getByText("Hello.");
    const style = el.getAttribute("style") ?? "";
    expect(style).toMatch(/opacity/);
    expect(style).toMatch(/blur/);
  });
});

describe("Paragraph", () => {
  it("renders each sentence with data-sid, drop cap flag on first", () => {
    const sentences = [
      { sid: "p1.s1", text: "Alpha." },
      { sid: "p1.s2", text: "Bravo." },
    ];
    render(
      <Paragraph
        paragraphIdx={1}
        sentences={sentences}
        fogStartSid={null}
        dropCap={true}
      />,
    );
    expect(document.querySelector('[data-sid="p1.s1"]')).not.toBeNull();
    expect(document.querySelector('[data-sid="p1.s2"]')).not.toBeNull();
    expect(document.querySelector(".rr-dropcap")).not.toBeNull();
  });
});
