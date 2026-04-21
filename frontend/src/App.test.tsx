import { render, screen } from "@testing-library/react";
import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { App } from "./App";

describe("App", () => {
  const originalFetch = globalThis.fetch;
  beforeEach(() => {
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve([]),
    }) as unknown as typeof fetch;
  });
  afterEach(() => {
    globalThis.fetch = originalFetch;
  });

  it("renders the Library screen at /", () => {
    render(<App />);
    expect(screen.getByText(/your shelf/i)).toBeInTheDocument();
    expect(screen.getByText("Library")).toBeInTheDocument();
  });
});
