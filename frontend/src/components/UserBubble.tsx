type UserBubbleProps = {
  text: string;
  pageAt?: number;
};

export function UserBubble({ text, pageAt }: UserBubbleProps) {
  return (
    <div
      data-role="user"
      style={{
        display: "flex",
        flexDirection: "column",
        alignItems: "flex-end",
        gap: 4,
        marginLeft: 48,
      }}
    >
      <div
        style={{
          background: "var(--paper-1)",
          color: "var(--ink-0)",
          padding: "12px 16px",
          borderRadius: "var(--r-lg)",
          borderBottomRightRadius: "var(--r-xs)",
          fontFamily: "var(--serif)",
          fontSize: 15,
          lineHeight: 1.55,
          maxWidth: "100%",
        }}
      >
        {text}
      </div>
      {pageAt != null && (
        <div
          style={{
            fontFamily: "var(--sans)",
            fontSize: 11,
            color: "var(--ink-3)",
            letterSpacing: 0.2,
            marginRight: 4,
          }}
        >
          asked at p. {pageAt}
        </div>
      )}
    </div>
  );
}
