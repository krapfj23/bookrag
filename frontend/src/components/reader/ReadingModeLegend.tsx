const items = [
  {
    label: "ASKED",
    swatch: "oklch(72% 0.08 155 / 0.6)",
    kind: "bg",
  },
  {
    label: "NOTED",
    swatch: "oklch(58% 0.1 55)",
    kind: "underline",
  },
  {
    label: "ENTITY",
    swatch: "oklch(60% 0.12 250 / 0.4)",
    kind: "bg",
  },
];

export function ReadingModeLegend() {
  return (
    <div
      data-testid="reading-mode-legend"
      style={{
        position: "fixed",
        bottom: 16,
        left: "50%",
        transform: "translateX(-50%)",
        display: "flex",
        gap: 20,
        alignItems: "center",
        background: "var(--paper-0, #fff)",
        border: "1px solid var(--ink-4, rgba(0,0,0,0.1))",
        borderRadius: 8,
        padding: "6px 16px",
        fontSize: 10.5,
        fontFamily: "var(--sans)",
        fontWeight: 600,
        letterSpacing: "0.08em",
        color: "var(--ink-2)",
        userSelect: "none",
        zIndex: 101,
      }}
    >
      {items.map((item) => (
        <span
          key={item.label}
          style={{ display: "flex", alignItems: "center", gap: 6 }}
        >
          {item.kind === "underline" ? (
            <span
              style={{
                display: "inline-block",
                width: 16,
                height: 2,
                background: item.swatch,
                borderRadius: 1,
              }}
            />
          ) : (
            <span
              style={{
                display: "inline-block",
                width: 16,
                height: 10,
                background: item.swatch,
                borderRadius: 2,
              }}
            />
          )}
          {item.label}
        </span>
      ))}
    </div>
  );
}
