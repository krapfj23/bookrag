import { NavBar } from "../components/NavBar";

export function UploadScreen() {
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
      </div>
    </div>
  );
}
