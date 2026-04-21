export type AssistantSource = {
  text: string;
  chapter: number;
};

type AssistantBubbleProps = {
  text: string;
  sources?: AssistantSource[];
  thinking?: boolean;
};

const MAX_SOURCES = 5;
const MAX_SOURCE_CHARS = 200;

function truncate(s: string, limit: number): string {
  return s.length > limit ? `${s.slice(0, limit)}…` : s;
}

export function AssistantBubble({
  text,
  sources,
  thinking = false,
}: AssistantBubbleProps) {
  const visibleSources = (sources ?? []).slice(0, MAX_SOURCES);
  return (
    <div
      data-role="assistant"
      style={{ display: "flex", gap: 12, marginRight: 48 }}
    >
      <div
        aria-hidden="true"
        style={{
          flexShrink: 0,
          width: 28,
          height: 28,
          borderRadius: 999,
          background: "var(--accent-softer)",
          color: "var(--accent)",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          fontFamily: "var(--serif)",
          fontStyle: "italic",
          fontSize: 13,
          fontWeight: 500,
          marginTop: 2,
        }}
      >
        r
      </div>
      <div style={{ flex: 1, minWidth: 0 }}>
        <div
          style={{
            fontFamily: "var(--serif)",
            fontSize: 15.5,
            lineHeight: 1.65,
            color: "var(--ink-0)",
          }}
        >
          {text}
          {thinking && (
            <span
              className="br-cursor"
              style={{
                display: "inline-block",
                width: 7,
                height: 15,
                background: "var(--accent)",
                marginLeft: 2,
                verticalAlign: -2,
                animation: "brBlink 1s steps(2) infinite",
              }}
            />
          )}
        </div>
        {visibleSources.length > 0 && (
          <div
            style={{
              marginTop: 12,
              display: "flex",
              flexDirection: "column",
              gap: 6,
            }}
          >
            {visibleSources.map((s, i) => (
              <div
                key={i}
                data-source-index={i}
                style={{
                  padding: "8px 12px",
                  borderLeft: "2px solid var(--accent)",
                  background: "var(--accent-softer)",
                  fontFamily: "var(--serif)",
                  fontSize: 13.5,
                  fontStyle: "italic",
                  lineHeight: 1.5,
                  color: "var(--ink-1)",
                }}
              >
                <span>{truncate(s.text, MAX_SOURCE_CHARS)}</span>
                <span
                  style={{
                    display: "inline-block",
                    marginLeft: 8,
                    fontFamily: "var(--sans)",
                    fontStyle: "normal",
                    fontSize: 11,
                    color: "var(--ink-2)",
                    letterSpacing: 0.2,
                  }}
                >
                  Ch. {s.chapter}
                </span>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
