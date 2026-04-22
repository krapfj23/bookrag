import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { NavBar } from "../components/NavBar";
import { Dropzone, type DropzoneState } from "../components/Dropzone";
import { PipelineRow } from "../components/PipelineRow";
import { Button } from "../components/Button";
import { ConnectionBanner } from "../components/ConnectionBanner";
import {
  uploadBook,
  fetchStatus,
  UploadError,
  type PipelineStage,
  type PipelineState,
  type StageName,
} from "../lib/api";
import type { BadgeState } from "../components/StatusBadge";

type StageDisplay = { key: StageName; label: string; desc: string };

const STAGE_DISPLAY: StageDisplay[] = [
  { key: "parse_epub", label: "Parse EPUB", desc: "Split into chapter-segmented text" },
  { key: "run_booknlp", label: "Run BookNLP", desc: "Entities, coreference, quotes" },
  {
    key: "resolve_coref",
    label: "Resolve coref",
    desc: "Parenthetical insertion pass",
  },
  {
    key: "discover_ontology",
    label: "Discover ontology",
    desc: "BERTopic + TF-IDF → OWL",
  },
  { key: "review_ontology", label: "Review ontology", desc: "Optional refinement" },
  {
    key: "run_cognee_batches",
    label: "Cognee batches",
    desc: "Claude extracts structured entities",
  },
  { key: "validate", label: "Validate", desc: "Spoiler-safety + spot checks" },
];

type Phase =
  | { kind: "idle" }
  | { kind: "uploading"; filename: string; file: File }
  | { kind: "error"; filename?: string; message: string }
  | {
      kind: "tracking";
      filename: string;
      book_id: string;
      pipelineState: PipelineState | null;
    };

function badgeFor(stage: PipelineStage | undefined): BadgeState {
  if (!stage) return "idle";
  switch (stage.status) {
    case "pending":
      return "idle";
    case "running":
      return "running";
    case "complete":
      return "done";
    case "failed":
      return "error";
  }
}

function metaFor(stage: PipelineStage | undefined): string | undefined {
  if (!stage) return undefined;
  if (stage.status === "complete" && typeof stage.duration_seconds === "number") {
    return formatSeconds(stage.duration_seconds);
  }
  if (stage.status === "failed") {
    return stage.error ?? "Failed";
  }
  return undefined;
}

function formatSeconds(s: number): string {
  if (s < 60) return `${s.toFixed(1)}s`;
  const m = Math.floor(s / 60);
  const rem = Math.round(s - m * 60);
  return `${m}m ${rem}s`;
}

function dropzoneState(phase: Phase): DropzoneState {
  switch (phase.kind) {
    case "idle":
      return "idle";
    case "uploading":
      return "uploading";
    case "error":
      return "error";
    case "tracking":
      return "done";
  }
}

function firstFailedStage(
  state: PipelineState | null,
): { name: StageName; stage: PipelineStage } | null {
  if (!state) return null;
  for (const d of STAGE_DISPLAY) {
    const s = state.stages[d.key];
    if (s && s.status === "failed") return { name: d.key, stage: s };
  }
  return null;
}

export function UploadScreen() {
  const [phase, setPhase] = useState<Phase>({ kind: "idle" });
  const stopPolling = useRef(false);
  const pollFailures = useRef(0);
  const [connectionLost, setConnectionLost] = useState(false);

  // Upload effect — fires when phase transitions to "uploading"
  useEffect(() => {
    if (phase.kind !== "uploading") return;
    const { file, filename } = phase;
    let cancelled = false;

    uploadBook(file)
      .then((resp) => {
        if (cancelled) return;
        setPhase({
          kind: "tracking",
          filename,
          book_id: resp.book_id,
          pipelineState: null,
        });
      })
      .catch((err: unknown) => {
        if (cancelled) return;
        const message =
          err instanceof UploadError
            ? err.message
            : err instanceof Error
              ? err.message
              : "Upload failed";
        setPhase({ kind: "error", filename, message });
      });

    return () => {
      cancelled = true;
    };
  }, [phase.kind === "uploading" ? phase.filename : null]); // eslint-disable-line react-hooks/exhaustive-deps

  // Polling effect — fires when phase transitions to "tracking"
  useEffect(() => {
    if (phase.kind !== "tracking") return;
    const book_id = phase.book_id;
    stopPolling.current = false;
    let cancelled = false;

    const tick = () => {
      fetchStatus(book_id)
        .then((next) => {
          if (cancelled) return;
          // Reset the failure counter + dismiss the banner on any success.
          pollFailures.current = 0;
          setConnectionLost(false);
          setPhase((prev) => {
            if (prev.kind !== "tracking" || prev.book_id !== book_id) return prev;
            return { ...prev, pipelineState: next };
          });
          if (
            next.ready_for_query ||
            Object.values(next.stages).some((s) => s.status === "failed")
          ) {
            stopPolling.current = true;
          }
        })
        .catch((err: unknown) => {
          if (cancelled) return;
          // Log every failure so outages are visible in devtools. Only
          // surface the banner after 3 consecutive misses so transient
          // blips don't flash an alert at the user.
          console.error("pipeline status poll failed", err);
          pollFailures.current += 1;
          if (pollFailures.current >= 3) setConnectionLost(true);
        });
    };

    const id = window.setInterval(() => {
      if (stopPolling.current) {
        window.clearInterval(id);
        return;
      }
      tick();
    }, 2000);

    return () => {
      cancelled = true;
      window.clearInterval(id);
    };
  }, [phase.kind === "tracking" ? phase.book_id : null]); // eslint-disable-line react-hooks/exhaustive-deps

  const trackingState = phase.kind === "tracking" ? phase.pipelineState : null;
  const failed = firstFailedStage(trackingState);
  const ready = trackingState?.ready_for_query === true;

  function handleFile(file: File) {
    stopPolling.current = false;
    pollFailures.current = 0;
    setConnectionLost(false);
    setPhase({ kind: "uploading", filename: file.name, file });
  }

  return (
    <div className="br" style={{ minHeight: "100vh", background: "var(--paper-0)" }}>
      <NavBar />
      <div style={{ maxWidth: 720, margin: "0 auto", padding: "64px 32px 80px" }}>
        <div
          style={{
            fontFamily: "var(--sans)",
            fontSize: 11,
            letterSpacing: 1.6,
            textTransform: "uppercase",
            color: "var(--ink-3)",
            marginBottom: 10,
          }}
        >
          Add a book
        </div>
        <h1
          style={{
            margin: "0 0 8px",
            fontFamily: "var(--serif)",
            fontWeight: 400,
            fontSize: 38,
            letterSpacing: -0.8,
            color: "var(--ink-0)",
          }}
        >
          Upload an EPUB.
        </h1>
        <div
          style={{
            fontFamily: "var(--serif)",
            fontSize: 17,
            lineHeight: 1.55,
            color: "var(--ink-2)",
            maxWidth: 520,
            marginBottom: 36,
          }}
        >
          We'll parse the chapters, learn the characters, and build a spoiler-aware
          index — so you can ask anything, and we'll answer only from what you've
          already read.
        </div>

        <Dropzone
          state={dropzoneState(phase)}
          filename={
            phase.kind === "uploading" ||
            phase.kind === "tracking" ||
            phase.kind === "error"
              ? phase.filename
              : undefined
          }
          errorMessage={phase.kind === "error" ? phase.message : undefined}
          onFile={handleFile}
        />

        {phase.kind === "tracking" && (
          <>
            <ConnectionBanner visible={connectionLost} />
            {failed && (
              <div
                role="alert"
                style={{
                  marginTop: 24,
                  padding: "12px 16px",
                  border: "1px solid var(--err)",
                  background: "color-mix(in oklab, var(--err) 8%, var(--paper-0))",
                  borderRadius: "var(--r-md)",
                  color: "var(--err)",
                  fontFamily: "var(--sans)",
                  fontSize: 13,
                }}
              >
                Pipeline failed at <strong>{failed.name}</strong>.
              </div>
            )}

            <div
              style={{
                marginTop: failed ? 16 : 40,
                padding: "24px 24px 8px",
                background: "var(--paper-00)",
                border: "var(--hairline)",
                borderRadius: "var(--r-lg)",
              }}
            >
              <div style={{ marginBottom: 16 }}>
                <div
                  style={{
                    fontFamily: "var(--mono)",
                    fontSize: 13,
                    color: "var(--ink-2)",
                    letterSpacing: 0.2,
                  }}
                >
                  {phase.book_id}
                </div>
              </div>

              {STAGE_DISPLAY.map((d) => (
                <PipelineRow
                  key={d.key}
                  title={d.label}
                  description={d.desc}
                  state={badgeFor(trackingState?.stages[d.key])}
                  meta={metaFor(trackingState?.stages[d.key])}
                />
              ))}
            </div>

            {ready && (
              <div
                style={{
                  marginTop: 20,
                  display: "flex",
                  justifyContent: "flex-end",
                }}
              >
                <Link to="/" style={{ textDecoration: "none" }}>
                  <Button variant="primary">Back to Library</Button>
                </Link>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}
