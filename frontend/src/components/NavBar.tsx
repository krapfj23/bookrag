import { Row } from "./layout";
import { Wordmark } from "./Wordmark";
import { IconBtn } from "./IconBtn";
import { IcMoon, IcSun, IcSettings } from "./icons";

export type NavTab = "library" | "reading" | "upload";

type NavBarProps = {
  active?: NavTab;
  theme?: "light" | "dark";
  onThemeToggle?: () => void;
};

const ITEMS: Array<{ id: NavTab; label: string }> = [
  { id: "library", label: "Library" },
  { id: "reading", label: "Reading" },
  { id: "upload", label: "Upload" },
];

export function NavBar({
  active = "library",
  theme = "light",
  onThemeToggle,
}: NavBarProps) {
  return (
    <header
      style={{
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        padding: "14px 28px",
        borderBottom: "var(--hairline)",
        background: "color-mix(in oklab, var(--paper-0) 80%, transparent)",
        backdropFilter: "saturate(140%) blur(12px)",
        fontFamily: "var(--sans)",
        height: 56,
        boxSizing: "border-box",
      }}
    >
      <Row gap={32}>
        <Wordmark />
        <nav style={{ display: "flex", gap: 4 }}>
          {ITEMS.map((it) => {
            const isActive = active === it.id;
            return (
              <a
                key={it.id}
                href="#"
                aria-current={isActive ? "page" : undefined}
                data-active={isActive ? "true" : "false"}
                onClick={(e) => e.preventDefault()}
                style={{
                  padding: "6px 12px",
                  fontSize: "var(--t-sm)",
                  color: isActive ? "var(--ink-0)" : "var(--ink-2)",
                  borderRadius: "var(--r-sm)",
                  fontWeight: isActive ? 500 : 400,
                  background: isActive ? "var(--paper-1)" : "transparent",
                  textDecoration: "none",
                  cursor: "pointer",
                  transition:
                    "color var(--dur) var(--ease), background var(--dur) var(--ease)",
                }}
              >
                {it.label}
              </a>
            );
          })}
        </nav>
      </Row>
      <Row gap={8}>
        <IconBtn onClick={onThemeToggle} title="Toggle theme">
          {theme === "dark" ? <IcSun size={15} /> : <IcMoon size={15} />}
        </IconBtn>
        <IconBtn title="Settings">
          <IcSettings size={15} />
        </IconBtn>
      </Row>
    </header>
  );
}
