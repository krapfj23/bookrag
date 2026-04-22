export function LatestExpandedDivider() {
  return (
    <div
      data-testid="latest-expanded-divider"
      style={{
        display: "flex",
        alignItems: "center",
        gap: 8,
        margin: "4px 0",
      }}
    >
      <div
        style={{
          flex: 1,
          height: 1,
          background: "var(--paper-2)",
        }}
      />
      <span
        style={{
          fontFamily: "var(--sans)",
          fontSize: 9.5,
          letterSpacing: 1.3,
          textTransform: "uppercase",
          color: "var(--ink-3)",
          whiteSpace: "nowrap",
        }}
      >
        Latest · expanded
      </span>
      <div
        style={{
          flex: 1,
          height: 1,
          background: "var(--paper-2)",
        }}
      />
    </div>
  );
}
