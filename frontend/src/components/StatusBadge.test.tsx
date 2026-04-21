import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import { StatusBadge } from "./StatusBadge";

describe("StatusBadge", () => {
  it("renders 'idle' with the idle label", () => {
    render(<StatusBadge state="idle" />);
    const badge = screen.getByRole("status");
    expect(badge).toHaveAttribute("aria-label", "idle");
    expect(badge).toHaveTextContent(/idle/i);
  });

  it("renders 'queued' with the queued label", () => {
    render(<StatusBadge state="queued" />);
    const badge = screen.getByRole("status");
    expect(badge).toHaveAttribute("aria-label", "queued");
    expect(badge).toHaveTextContent(/queued/i);
  });

  it("renders 'running' with a pulsing indicator", () => {
    render(<StatusBadge state="running" />);
    const badge = screen.getByRole("status");
    expect(badge).toHaveAttribute("aria-label", "running");
    expect(badge).toHaveTextContent(/running/i);
    const dot = badge.querySelector("[data-pulse='true']");
    expect(dot).toBeTruthy();
  });

  it("renders 'done'", () => {
    render(<StatusBadge state="done" />);
    const badge = screen.getByRole("status");
    expect(badge).toHaveAttribute("aria-label", "done");
    expect(badge).toHaveTextContent(/done/i);
  });

  it("renders 'error' with the 'failed' label", () => {
    render(<StatusBadge state="error" />);
    const badge = screen.getByRole("status");
    expect(badge).toHaveAttribute("aria-label", "failed");
    expect(badge).toHaveTextContent(/failed/i);
  });

  it("honors a custom label override", () => {
    render(<StatusBadge state="running" label="building — 3 of 7" />);
    expect(screen.getByRole("status")).toHaveTextContent(/building — 3 of 7/);
  });
});
