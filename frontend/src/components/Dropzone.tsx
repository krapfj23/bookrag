import {
  useRef,
  useState,
  type CSSProperties,
  type DragEvent,
  type ChangeEvent,
} from "react";
import { IcUpload, IcCheck, IcClose } from "./icons";

export type DropzoneState = "idle" | "hover" | "uploading" | "done" | "error";

type DropzoneProps = {
  state: DropzoneState;
  filename?: string;
  errorMessage?: string;
  onFile: (file: File) => void;
};

export function Dropzone({ state, filename, errorMessage, onFile }: DropzoneProps) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [dragOver, setDragOver] = useState(false);

  const busy = state === "uploading";
  const isHover = state === "hover" || dragOver;
  const isDone = state === "done";
  const isError = state === "error";

  const border = isError
    ? "1.5px dashed var(--err)"
    : `1.5px dashed ${isHover ? "var(--accent)" : "var(--paper-3)"}`;

  const bg = isError
    ? "color-mix(in oklab, var(--err) 8%, var(--paper-00))"
    : isHover
      ? "var(--accent-softer)"
      : "var(--paper-00)";

  const iconBg = isDone
    ? "var(--ok)"
    : isError
      ? "var(--err)"
      : isHover || busy
        ? "var(--accent)"
        : "var(--paper-1)";

  const iconFg =
    isDone || isError || isHover || busy ? "var(--paper-00)" : "var(--ink-2)";

  const primaryCopy = (() => {
    if (isError) return filename ?? "Something went wrong";
    if (isDone) return filename ?? "Upload complete";
    if (busy) return filename ?? "Uploading…";
    if (isHover) return "Drop it here";
    return "Drop your EPUB";
  })();

  const secondaryCopy = (() => {
    if (isError) return null;
    if (isDone) return "Uploaded";
    if (busy) return "Uploading…";
    return null;
  })();

  function handleDragOver(e: DragEvent<HTMLDivElement>) {
    e.preventDefault();
    if (!busy) setDragOver(true);
  }
  function handleDragLeave(e: DragEvent<HTMLDivElement>) {
    e.preventDefault();
    setDragOver(false);
  }
  function handleDrop(e: DragEvent<HTMLDivElement>) {
    e.preventDefault();
    setDragOver(false);
    if (busy) return;
    const f = e.dataTransfer.files?.[0];
    if (f) onFile(f);
  }
  function handleClick() {
    if (busy) return;
    inputRef.current?.click();
  }
  function handleChange(e: ChangeEvent<HTMLInputElement>) {
    const f = e.target.files?.[0];
    if (f) onFile(f);
    // allow the same file to be picked again later
    e.target.value = "";
  }

  const rootStyle: CSSProperties = {
    border,
    background: bg,
    borderRadius: "var(--r-lg)",
    padding: "56px 40px",
    textAlign: "center",
    fontFamily: "var(--sans)",
    color: "var(--ink-1)",
    transition: "all var(--dur) var(--ease)",
    cursor: busy ? "progress" : "pointer",
  };

  return (
    <div
      data-testid="dropzone"
      data-state={state}
      onClick={handleClick}
      onDragOver={handleDragOver}
      onDragLeave={handleDragLeave}
      onDrop={handleDrop}
      style={rootStyle}
    >
      <div
        style={{
          display: "inline-flex",
          alignItems: "center",
          justifyContent: "center",
          width: 44,
          height: 44,
          borderRadius: 999,
          background: iconBg,
          color: iconFg,
          marginBottom: 16,
          transition: "all var(--dur) var(--ease)",
        }}
      >
        {isDone ? (
          <IcCheck size={18} />
        ) : isError ? (
          <IcClose size={18} />
        ) : (
          <IcUpload size={18} />
        )}
      </div>

      <div
        style={{
          fontFamily: "var(--serif)",
          fontSize: 20,
          color: "var(--ink-0)",
          letterSpacing: -0.3,
          marginBottom: 6,
        }}
      >
        {primaryCopy}
      </div>

      {isError ? (
        <div role="alert" style={{ fontSize: 13, color: "var(--err)" }}>
          {errorMessage ?? "Something went wrong"}
        </div>
      ) : secondaryCopy ? (
        <div style={{ fontSize: 13, color: "var(--ink-2)" }}>{secondaryCopy}</div>
      ) : (
        <div style={{ fontSize: 13, color: "var(--ink-2)" }}>
          or{" "}
          <span
            style={{
              color: "var(--accent)",
              textDecoration: "underline",
              textUnderlineOffset: 3,
            }}
          >
            browse files
          </span>{" "}
          · EPUB up to 500&nbsp;MB
        </div>
      )}

      <input
        ref={inputRef}
        data-testid="dropzone-input"
        type="file"
        accept=".epub,application/epub+zip"
        onChange={handleChange}
        style={{ display: "none" }}
      />
    </div>
  );
}
