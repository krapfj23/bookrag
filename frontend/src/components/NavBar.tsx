import { Link, useLocation } from "react-router-dom";
import { Row } from "./layout";
import { Wordmark } from "./Wordmark";
import { IconBtn } from "./IconBtn";
import { IcMoon, IcSun, IcSettings } from "./icons";

export type NavTab = "library" | "reading" | "upload";

type NavBarProps = {
  theme?: "light" | "dark";
  onThemeToggle?: () => void;
};

type Item =
  | { id: NavTab; label: string; to: string; inert?: false }
  | { id: NavTab; label: string; to?: undefined; inert: true };

const ITEMS: Item[] = [
  { id: "library", label: "Library", to: "/" },
  { id: "reading", label: "Reading", inert: true },
  { id: "upload", label: "Upload", to: "/upload" },
];

function tabForPath(pathname: string): NavTab {
  if (pathname === "/upload" || pathname.startsWith("/upload/")) return "upload";
  if (pathname.startsWith("/books/")) return "reading";
  return "library";
}

export function NavBar({ theme = "light", onThemeToggle }: NavBarProps) {
  const { pathname } = useLocation();
  const active = tabForPath(pathname);

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
            const baseStyle: React.CSSProperties = {
              padding: "6px 12px",
              fontSize: "var(--t-sm)",
              color: isActive ? "var(--ink-0)" : "var(--ink-2)",
              borderRadius: "var(--r-sm)",
              fontWeight: isActive ? 500 : 400,
              background: isActive ? "var(--paper-1)" : "transparent",
              textDecoration: "none",
              cursor: it.inert ? "default" : "pointer",
              transition:
                "color var(--dur) var(--ease), background var(--dur) var(--ease)",
            };

            if (it.inert) {
              return (
                <a
                  key={it.id}
                  href="#"
                  aria-disabled="true"
                  data-active={isActive ? "true" : "false"}
                  onClick={(e) => e.preventDefault()}
                  style={baseStyle}
                >
                  {it.label}
                </a>
              );
            }

            return (
              <Link
                key={it.id}
                to={it.to}
                aria-current={isActive ? "page" : undefined}
                data-active={isActive ? "true" : "false"}
                style={baseStyle}
              >
                {it.label}
              </Link>
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
