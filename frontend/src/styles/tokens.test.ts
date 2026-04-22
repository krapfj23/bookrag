/**
 * T17 — Token-drift guard.
 * Asserts that the literal text of tokens.css contains the expected --accent
 * value so accidental drift is caught at test time.
 */
import { describe, it, expect } from "vitest";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";

const cssPath = resolve(__dirname, "tokens.css");
const rawCss = readFileSync(cssPath, "utf-8");

describe("tokens.css drift guard", () => {
  it("--accent is oklch(62% 0.045 145)", () => {
    // The canonical value for the sage accent in light mode.
    expect(rawCss).toMatch(/--accent:\s*oklch\(62%\s+0\.045\s+145\)/);
  });
});
