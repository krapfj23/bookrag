import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
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

  it("applies asked background when marks include ask", () => {
    render(
      <Sentence
        sid="p1.s1"
        text="X."
        fogged={false}
        marks={[{ kind: "ask", cardId: "a1" }]}
      />,
    );
    const el = screen.getByText("X.");
    expect(el.getAttribute("style") ?? "").toMatch(/background/);
  });

  it("applies underline when marks include note", () => {
    render(
      <Sentence
        sid="p1.s1"
        text="X."
        fogged={false}
        marks={[{ kind: "note", cardId: "n1" }]}
      />,
    );
    const el = screen.getByText("X.");
    expect(el.getAttribute("style") ?? "").toMatch(/underline/);
  });

  it("fires onMarkClick with topmost mark's cardId", async () => {
    const fn = vi.fn();
    render(
      <Sentence
        sid="p1.s1"
        text="X."
        fogged={false}
        marks={[{ kind: "ask", cardId: "a1" }]}
        onMarkClick={fn}
      />,
    );
    await userEvent.click(screen.getByText("X."));
    expect(fn).toHaveBeenCalledWith("a1");
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
