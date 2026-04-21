import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import { PipelineRow } from "./PipelineRow";

describe("PipelineRow", () => {
  it("renders title, description, and a StatusBadge", () => {
    render(
      <PipelineRow title="Parse EPUB" description="Split into chapter-segmented text" state="idle" />
    );
    expect(screen.getByText("Parse EPUB")).toBeInTheDocument();
    expect(screen.getByText(/split into chapter-segmented text/i)).toBeInTheDocument();
    expect(screen.getByRole("status")).toHaveAttribute("aria-label", "idle");
  });

  it("shows meta when state is 'done'", () => {
    render(
      <PipelineRow
        title="Parse EPUB"
        description="Split into chapter-segmented text"
        state="done"
        meta="0.4s"
      />
    );
    expect(screen.getByText("0.4s")).toBeInTheDocument();
    expect(screen.getByRole("status")).toHaveAttribute("aria-label", "done");
  });

  it("shows meta when state is 'error'", () => {
    render(
      <PipelineRow
        title="Validate"
        description="Spoiler-safety + spot checks"
        state="error"
        meta="OOM killed"
      />
    );
    expect(screen.getByText(/oom killed/i)).toBeInTheDocument();
    expect(screen.getByRole("status")).toHaveAttribute("aria-label", "failed");
  });

  it("does not render meta when state is 'idle' and meta is omitted", () => {
    const { container } = render(
      <PipelineRow
        title="Review ontology"
        description="Optional refinement"
        state="idle"
      />
    );
    expect(container.querySelector("[data-pipeline-meta]")).toBeNull();
  });
});
