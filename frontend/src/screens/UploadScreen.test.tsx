import { render, screen, fireEvent, waitFor, act } from "@testing-library/react";
import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { MemoryRouter } from "react-router-dom";
import { UploadScreen } from "./UploadScreen";
import * as api from "../lib/api";
import type { PipelineState, StageName } from "../lib/api";

const BOOK_ID = "a_christmas_carol_a1b2c3d4";

function stagesWith(overrides: Partial<Record<StageName, api.PipelineStage>> = {}): PipelineState["stages"] {
  const base: PipelineState["stages"] = {
    parse_epub: { status: "pending" },
    run_booknlp: { status: "pending" },
    resolve_coref: { status: "pending" },
    discover_ontology: { status: "pending" },
    review_ontology: { status: "pending" },
    run_cognee_batches: { status: "pending" },
    validate: { status: "pending" },
  };
  return { ...base, ...overrides };
}

function mkState(over: Partial<PipelineState> = {}): PipelineState {
  return {
    book_id: BOOK_ID,
    status: "processing",
    stages: stagesWith(),
    current_batch: null,
    total_batches: null,
    ready_for_query: false,
    ...over,
  };
}

function makeEpub(name = "a-christmas-carol.epub"): File {
  return new File([new Uint8Array([0x50, 0x4b, 0x03, 0x04])], name, {
    type: "application/epub+zip",
  });
}

function renderScreen() {
  return render(
    <MemoryRouter initialEntries={["/upload"]}>
      <UploadScreen />
    </MemoryRouter>
  );
}

describe("UploadScreen", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });
  afterEach(() => {
    vi.runOnlyPendingTimers();
    vi.useRealTimers();
    vi.restoreAllMocks();
  });

  it("renders the header, tagline, and idle Dropzone", () => {
    renderScreen();
    expect(screen.getByText(/add a book/i)).toBeInTheDocument();
    expect(screen.getByText(/upload an epub\./i)).toBeInTheDocument();
    expect(screen.getByText(/we'll parse the chapters/i)).toBeInTheDocument();
    expect(screen.getByText(/drop your epub/i)).toBeInTheDocument();
  });

  it("uploads the dropped file, then polls and renders the 7 stages", async () => {
    const uploadSpy = vi.spyOn(api, "uploadBook").mockResolvedValue({
      book_id: BOOK_ID,
      message: "Pipeline started",
    });
    const statusSpy = vi.spyOn(api, "fetchStatus").mockResolvedValue(
      mkState({
        stages: stagesWith({
          parse_epub: { status: "complete", duration_seconds: 0.4 },
          run_booknlp: { status: "running" },
        }),
      })
    );

    renderScreen();

    const zone = screen.getByTestId("dropzone");
    await act(async () => {
      fireEvent.drop(zone, { dataTransfer: { files: [makeEpub()] } });
    });

    await waitFor(() => expect(uploadSpy).toHaveBeenCalledTimes(1));

    // Filename and book_id appear
    await waitFor(() => {
      expect(screen.getAllByText("a-christmas-carol.epub").length).toBeGreaterThanOrEqual(1);
      expect(screen.getByText(BOOK_ID)).toBeInTheDocument();
    });

    // Let polling run for 6 seconds to pin the ~2s cadence:
    // an implementation that polls every 500ms would produce >= 12 calls and fail.
    await act(async () => {
      await vi.advanceTimersByTimeAsync(6000);
    });

    // 3 calls (2000/4000/6000) or 4 calls (immediate + 2000/4000/6000) is acceptable;
    // anything outside that range implies the cadence is wrong.
    expect(statusSpy.mock.calls.length).toBeGreaterThanOrEqual(3);
    expect(statusSpy.mock.calls.length).toBeLessThanOrEqual(4);

    // Row labels render in pipeline order.
    const labels = screen
      .getAllByText(
        /^(Parse EPUB|Run BookNLP|Resolve coref|Discover ontology|Review ontology|Cognee batches|Validate)$/,
      )
      .map((n) => n.textContent);
    expect(labels).toEqual([
      "Parse EPUB",
      "Run BookNLP",
      "Resolve coref",
      "Discover ontology",
      "Review ontology",
      "Cognee batches",
      "Validate",
    ]);
  });

  it("stops polling and renders 'Back to Library' when ready_for_query becomes true", async () => {
    vi.spyOn(api, "uploadBook").mockResolvedValue({
      book_id: BOOK_ID,
      message: "Pipeline started",
    });
    const statusSpy = vi
      .spyOn(api, "fetchStatus")
      .mockResolvedValueOnce(
        mkState({
          stages: stagesWith({ parse_epub: { status: "running" } }),
        })
      )
      .mockResolvedValueOnce(
        mkState({
          status: "complete",
          ready_for_query: true,
          stages: stagesWith({
            parse_epub: { status: "complete", duration_seconds: 0.4 },
            run_booknlp: { status: "complete", duration_seconds: 38 },
            resolve_coref: { status: "complete", duration_seconds: 12 },
            discover_ontology: { status: "complete" },
            review_ontology: { status: "complete" },
            run_cognee_batches: { status: "complete" },
            validate: { status: "complete" },
          }),
        })
      );

    renderScreen();
    const zone = screen.getByTestId("dropzone");
    await act(async () => {
      fireEvent.drop(zone, { dataTransfer: { files: [makeEpub()] } });
    });

    await act(async () => {
      await vi.advanceTimersByTimeAsync(2000);
    });
    await act(async () => {
      await vi.advanceTimersByTimeAsync(2000);
    });

    await waitFor(() => {
      expect(screen.getByRole("link", { name: /back to library/i })).toBeInTheDocument();
    });
    expect(screen.getByRole("link", { name: /back to library/i })).toHaveAttribute(
      "href",
      "/"
    );

    const callsAtReady = statusSpy.mock.calls.length;
    await act(async () => {
      await vi.advanceTimersByTimeAsync(4000);
    });
    expect(statusSpy.mock.calls.length).toBe(callsAtReady);
  });

  it("stops polling and shows an error banner when any stage fails", async () => {
    vi.spyOn(api, "uploadBook").mockResolvedValue({
      book_id: BOOK_ID,
      message: "Pipeline started",
    });
    const statusSpy = vi.spyOn(api, "fetchStatus").mockResolvedValue(
      mkState({
        status: "failed",
        stages: stagesWith({
          parse_epub: { status: "complete", duration_seconds: 0.4 },
          run_booknlp: { status: "failed", error: "OOM killed" },
        }),
      })
    );

    renderScreen();
    const zone = screen.getByTestId("dropzone");
    await act(async () => {
      fireEvent.drop(zone, { dataTransfer: { files: [makeEpub()] } });
    });
    await act(async () => {
      await vi.advanceTimersByTimeAsync(2000);
    });

    await waitFor(() => {
      expect(screen.getByRole("alert")).toHaveTextContent(/pipeline failed/i);
    });
    expect(screen.getByText(/oom killed/i)).toBeInTheDocument();
    // Last-known state of already-completed stages must survive the failure.
    expect(screen.getByText("0.4s")).toBeInTheDocument();

    const callsAtFail = statusSpy.mock.calls.length;
    await act(async () => {
      await vi.advanceTimersByTimeAsync(4000);
    });
    expect(statusSpy.mock.calls.length).toBe(callsAtFail);
  });

  it("shows the mapped error in the Dropzone when uploadBook rejects", async () => {
    vi.spyOn(api, "uploadBook").mockRejectedValue(
      new api.UploadError(400, "Only .epub files are accepted")
    );

    renderScreen();
    const zone = screen.getByTestId("dropzone");
    await act(async () => {
      fireEvent.drop(zone, { dataTransfer: { files: [makeEpub("nope.txt")] } });
    });

    await waitFor(() => {
      expect(screen.getByRole("alert")).toHaveTextContent(
        /only \.epub files are accepted/i
      );
    });
  });
});
