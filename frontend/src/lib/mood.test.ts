import { describe, it, expect } from "vitest";
import { moodForBookId, MOODS } from "./mood";

describe("moodForBookId", () => {
  it("returns one of the 6 moods", () => {
    expect(MOODS).toEqual(["sage", "amber", "slate", "rose", "charcoal", "paper"]);
    expect(MOODS).toContain(moodForBookId("christmas_carol_e6ddcd76"));
  });

  it("is stable — same input → same output across calls", () => {
    const a = moodForBookId("christmas_carol_e6ddcd76");
    const b = moodForBookId("christmas_carol_e6ddcd76");
    expect(a).toBe(b);
  });

  it("is deterministic across different inputs", () => {
    expect(moodForBookId("red_rising_abc12345")).toBe(
      moodForBookId("red_rising_abc12345")
    );
  });

  it("handles empty string", () => {
    expect(MOODS).toContain(moodForBookId(""));
  });
});
