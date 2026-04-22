/**
 * T3 — S1EmptyCard: 3 suggested questions with mono bullets + IcSpark icon.
 */
import { describe, it, expect } from "vitest";
import { render } from "@testing-library/react";
import { S1EmptyCard } from "./S1EmptyCard";

describe("S1EmptyCard T3 — suggested questions list", () => {
  it("renders exactly 3 list items", () => {
    const { getAllByRole } = render(<S1EmptyCard />);
    const items = getAllByRole("listitem");
    expect(items).toHaveLength(3);
  });

  it("each list item has a numeral span with mono font-family", () => {
    const { container } = render(<S1EmptyCard />);
    const bullets = container.querySelectorAll('[data-testid^="bullet-"]');
    expect(bullets).toHaveLength(3);
    for (const bullet of bullets) {
      const style = (bullet as HTMLElement).getAttribute("style") ?? "";
      expect(style.toLowerCase()).toMatch(/plex mono|mono/i);
    }
  });
});

describe("S1EmptyCard T3 — IcSpark icon", () => {
  it("renders an SVG with the IcSpark path inside the badge", () => {
    const { container } = render(<S1EmptyCard />);
    const paths = container.querySelectorAll(
      '[data-testid="s1-empty-card"] svg path'
    );
    expect(paths.length).toBeGreaterThan(0);
    const sparkPath = Array.from(paths).find((p) =>
      (p.getAttribute("d") ?? "").includes("M8 2v3")
    );
    expect(sparkPath).toBeTruthy();
  });
});
