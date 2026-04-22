const ORDINALS = ["One", "Two", "Three", "Four", "Five", "Six", "Seven", "Eight", "Nine", "Ten"];

function ordinal(n: number): string {
  return ORDINALS[n - 1] ?? String(n);
}

export function PacingLabel({ num, total }: { num: number; total: number }) {
  return (
    <div
      data-testid="pacing-label"
      style={{
        fontFamily: "var(--serif)",
        fontStyle: "italic",
        fontSize: "12px",
        color: "var(--ink-3)",
        letterSpacing: "1.4px",
        textTransform: "uppercase",
        userSelect: "none",
      }}
    >
      {`Stave ${ordinal(num)} · of ${ordinal(total)}`}
    </div>
  );
}
