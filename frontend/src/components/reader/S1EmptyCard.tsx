import { IcSpark } from "../icons";

const SUGGESTED_QUESTIONS = [
  "Who is this character?",
  "What just happened here?",
  "What does this phrase mean?",
];

export function S1EmptyCard() {
  return (
    <article
      data-testid="s1-empty-card"
      style={{
        background: "var(--paper-00)",
        border: "1px solid var(--paper-2)",
        borderRadius: 10,
        padding: "18px 18px 16px",
        boxShadow: "0 4px 12px -4px rgba(28,24,18,.06)",
        display: "grid",
        gridTemplateColumns: "34px 1fr",
        gap: 12,
      }}
    >
      <div
        aria-hidden="true"
        style={{
          width: 34,
          height: 34,
          borderRadius: 999,
          background: "var(--accent-softer)",
          display: "grid",
          placeItems: "center",
          color: "var(--accent-ink)",
        }}
      >
        <IcSpark size={16} />
      </div>
      <div>
        <h3
          style={{
            fontFamily: "var(--serif)",
            fontWeight: 500,
            fontSize: 15,
            margin: "2px 0 10px",
            color: "var(--ink-0)",
          }}
        >
          Ask about what you're reading
        </h3>
        <ol
          style={{
            listStyle: "none",
            padding: 0,
            margin: 0,
          }}
        >
          {SUGGESTED_QUESTIONS.map((q, i) => (
            <li
              key={q}
              style={{
                display: "grid",
                gridTemplateColumns: "auto 1fr",
                gap: 8,
                marginBottom: 6,
              }}
            >
              <span
                data-testid={`bullet-${i + 1}`}
                style={{
                  fontFamily: "IBM Plex Mono, SF Mono, ui-monospace, monospace",
                  fontSize: 11,
                  color: "var(--ink-3)",
                  lineHeight: "1.72",
                }}
              >
                {i + 1}.
              </span>
              <span
                style={{
                  fontFamily: "var(--serif)",
                  fontSize: 13.5,
                  color: "var(--ink-1)",
                  lineHeight: 1.5,
                }}
              >
                {q}
              </span>
            </li>
          ))}
        </ol>
      </div>
    </article>
  );
}
