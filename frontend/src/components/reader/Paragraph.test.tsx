import { describe, it, expect } from "vitest";
import { render } from "@testing-library/react";
import { Paragraph } from "./Paragraph";

const sentences = [
  { sid: "p1.s1", text: "Hello world." },
  { sid: "p1.s2", text: "Second sentence." },
];

describe("Paragraph — kind variants", () => {
  it("renders a body paragraph by default", () => {
    const { container } = render(
      <Paragraph
        paragraphIdx={1}
        sentences={sentences}
        fogStartSid={null}
        dropCap={false}
      />,
    );
    const p = container.querySelector("p");
    expect(p).not.toBeNull();
    expect(p!.className).toContain("rr-para");
    expect(p!.className).not.toContain("rr-scene-break");
    expect(p!.className).not.toContain("rr-epigraph");
  });

  it("renders a scene break as a centered dinkus ornament", () => {
    const { container } = render(
      <Paragraph
        paragraphIdx={3}
        sentences={[{ sid: "p3.s1", text: "***" }]}
        fogStartSid={null}
        dropCap={false}
        kind="scene_break"
      />,
    );
    const p = container.querySelector("p.rr-scene-break");
    expect(p).not.toBeNull();
    expect(p!.getAttribute("aria-hidden")).toBe("true");
    expect(p!.textContent).toContain("* * *");
  });

  it("keeps data-sid on the scene-break span so cards can anchor", () => {
    const { container } = render(
      <Paragraph
        paragraphIdx={3}
        sentences={[{ sid: "p3.s1", text: "***" }]}
        fogStartSid={null}
        dropCap={false}
        kind="scene_break"
      />,
    );
    const span = container.querySelector("p.rr-scene-break > span");
    expect(span).not.toBeNull();
    expect(span!.getAttribute("data-sid")).toBe("p3.s1");
  });

  it("renders an epigraph with italic styling class", () => {
    const { container } = render(
      <Paragraph
        paragraphIdx={1}
        sentences={sentences}
        fogStartSid={null}
        dropCap={false}
        kind="epigraph"
      />,
    );
    const p = container.querySelector("p.rr-epigraph");
    expect(p).not.toBeNull();
    expect(p!.className).not.toContain("rr-dropcap");
  });

  it("epigraph class wins over drop cap", () => {
    const { container } = render(
      <Paragraph
        paragraphIdx={1}
        sentences={sentences}
        fogStartSid={null}
        dropCap={true}
        kind="epigraph"
      />,
    );
    const p = container.querySelector("p");
    expect(p!.className).toContain("rr-epigraph");
    expect(p!.className).not.toContain("rr-dropcap");
  });
});
