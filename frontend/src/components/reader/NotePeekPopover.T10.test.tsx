/**
 * T10 — NotePeekPopover full redesign: 360px, orange border-left, paper-00,
 * 10px radius, shadow, "ago" meta.
 */
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { NotePeekPopover } from "./NotePeekPopover";

describe("NotePeekPopover T10 — visual spec", () => {
  it("has width 360px in style", () => {
    render(<NotePeekPopover visible body="hello" x={100} y={100} createdAt="" />);
    const el = screen.getByTestId("note-peek");
    const style = el.getAttribute("style") ?? "";
    expect(style).toMatch(/width:\s*360px/);
  });

  it("has orange border-left 3px in style", () => {
    render(<NotePeekPopover visible body="hello" x={100} y={100} createdAt="" />);
    const el = screen.getByTestId("note-peek");
    const style = el.getAttribute("style") ?? "";
    expect(style).toMatch(/border-left/);
    expect(style).toMatch(/3px/);
  });

  it("has border-radius 10px in style", () => {
    render(<NotePeekPopover visible body="hello" x={100} y={100} createdAt="" />);
    const el = screen.getByTestId("note-peek");
    const style = el.getAttribute("style") ?? "";
    expect(style).toMatch(/border-radius:\s*10px/);
  });

  it("renders a meta line containing relative time text", () => {
    render(<NotePeekPopover visible body="hello" x={100} y={100} createdAt="" />);
    const el = screen.getByTestId("note-peek");
    // The meta line contains some relative time text
    expect(el.textContent).toMatch(/ago|just now/i);
  });
});
