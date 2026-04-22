# Handoff: BookRAG Reader UI

## Overview

BookRAG is a browser-based EPUB reader with an integrated AI-assisted annotation layer. Users read books as paginated two-page spreads, highlight phrases to **ask** questions (RAG-answered) or add **notes**, and those annotations appear as margin cards beside the text. A **reading mode** hides the margin column, leaving only subtle indicators (green highlights, underlines) on the page itself.

This handoff covers the **reader + chat surface** only. The EPUB ingestion pipeline and storage layer (kuzudb) are already implemented — see your backend `CLAUDE.md`.

## About the design files

**The HTML files in this bundle are design references — prototypes showing intended look and behavior, not production code.** They were built in vanilla React + Babel to iterate on visual decisions quickly.

Your job: **recreate these designs in the target codebase's existing environment** (React/Vite, Next.js, etc.) using the project's established patterns, libraries, and routing. If no frontend environment exists yet, React + Vite is a reasonable default.

**Do not port the `.jsx` prototype files literally.** Lift patterns and exact visual values (colors, spacing, type) but rebuild the components following the target codebase's conventions.

## Fidelity

**High-fidelity (hifi).** Pixel-level decisions are made. Colors, typography, spacing, interaction states, and animations are all specified in the visualizer and design system. Reproduce them precisely.

## Decisions (locked)

See `Handoff Spec.html` for the full table. Quick reference:

| Decision | Value |
|---|---|
| Chat direction | **V3 Inline** — margin note-cards |
| Reading mode | **Ambitious** — ambient paper, pacing label, hover note-peek |
| Overflow strategy | **O2 Collapse** — older cards → 1-line summaries, latest expanded |
| Platform | Desktop browser only (v1) |
| Keyboard | Arrow keys only for page turns |
| Streaming | Token-by-token |
| Reading mode persistence | localStorage per-book |
| URL shape | `/book/{bookId}` — rest in localStorage |
| Data model | Cards separate as `ask` (Q+A) or `note` (body only) |
| Fog of war | Only ask about text before the reading cursor |
| Storage/sync | Local-only (single user, single device) |
| DRM | Unencrypted EPUBs only |

## Screens / views

### 1. Reading surface — V3 Inline (default)

**Purpose:** The primary reading experience. User reads the book with their annotations visible in the right margin.

**Layout:**
- Top bar: 52px tall, three-column grid (Library back · Title · Actions). `padding: 14px 28px`.
- Stage: CSS grid, `grid-template-columns: 1fr 400px`, `gap: 28px`, padded `0 24px`.
- Book: two-page spread, left + right pages side by side, each with `padding: 52px 44px 40px`.
- Right column: V3 Inline margin cards, `padding-top: 40px`, `gap: 14px` between cards.

**Components on the page:**
- **Top bar** — back link `← Library`, book title italic serif, `Search` + `Bookmark` + `Ask` pill icons on the right. Ask pill uses `var(--accent)` background with white text.
- **Book spread** — `BookSpread` component. `background: var(--paper-00)`, `box-shadow: 0 30px 70px -24px rgba(28,24,18,.2), 0 10px 20px -8px rgba(28,24,18,.08)`, `border-radius: 3px`.
  - Chapter stave tag: italic serif, 11.5px, `var(--ink-3)`, `letter-spacing: 0.4px`.
  - Chapter title: serif, 22px, `letter-spacing: -0.3px`, weight 400.
  - Body: serif, 15px, `line-height: 1.72`, `text-align: justify`, `hyphens: auto`, `var(--ink-0)`.
  - Drop-cap on first paragraph: 54px serif, floated left, `padding: 4px 8px 0 0`.
  - Folio (page number + author): italic serif, 11px, `var(--ink-3)`, mono font for numerals.
  - Spine gradient: absolutely positioned 30px-wide strip at 50% horizontal, `linear-gradient(to right, transparent 0%, color-mix(in oklab, var(--ink-0) 7%, transparent) 50%, transparent 100%)`.
- **Margin cards (asks):** `background: var(--paper-00)`, `border: 1px solid var(--paper-2)`, `border-left: 3px solid var(--accent)`, `border-radius: 10px`, `padding: 14px 16px`, `box-shadow: 0 4px 12px -4px rgba(28,24,18,.08)`, rotated `-0.3deg` to `0.3deg` for a handwritten feel.
  - Header strip: 9.5px, uppercase, `letter-spacing: 1.3px`, `var(--accent-ink)`, weight 600. Text: `ASKED ABOUT "{quote}" · p. {page}`.
  - Question: italic serif, 13.5px, `var(--ink-1)`.
  - Answer: serif, 14px, `line-height: 1.62`, `var(--ink-0)`.
- **Margin cards (notes):** Same as asks but `border-left: 3px solid oklch(58% 0.1 55)` (warm orange-brown) and header strip color `oklch(30% 0.1 55)`.

**Highlight & annotation indicators on text:**
- Asked phrases: `background: oklch(72% 0.08 155 / 0.42)` (dark green), `padding: 1px 3px`, `border-radius: 2px`.
- Noted phrases: `text-decoration: underline`, `text-decoration-color: oklch(58% 0.1 55)`, `thickness: 1.5px`, `underline-offset: 3px`.
- Entity links: `text-decoration: underline dotted var(--accent)`, `underline-offset: 3px`.

### 2. Card states (atomic)

See visualizer section "V3 Inline · atomic states" (S1–S7). Reproduce each:

- **S1 Empty** — no cards yet. Right column shows an invitation card: sparkle icon badge (34×34, `var(--accent-softer)` bg), serif heading "Ask about what you're reading", 3 suggested questions with mono-numeral bullets.
- **S2 Single** — one card, faint SVG connector (dashed, `var(--accent)` at 0.6 opacity) from card to the highlighted phrase on the page.
- **S3 Streaming** — typing cursor at end of answer (6×14px `var(--ink-2)` block, `animation: blink 1s infinite`). Plus a skeleton placeholder card with "THINKING · gathering 3 more passages" label.
- **S4 Long answer** — `max-height: 220px`, `overflow: auto` inside the card. Fade gradient at bottom edge.
- **S5 Thread** — follow-up replies indented by 14px with a `1px dashed var(--paper-3)` left border. Header label "FOLLOW-UP" in uppercase 9.5px.
- **S6 Off-screen anchor** — card has `↑ SCROLL UP ·` prefix in its header. A vertical colored bar on the book's right edge indicates the anchor's location. Below the card, a small CTA: "Jump to anchor on this page" with `var(--accent-softer)` background + dashed `var(--accent)` border.
- **S7 Cross-page** — card has `← FROM p. 1 ·` prefix; otherwise identical.

### 3. Overflow — O2 Collapse

When >2 cards on a spread: older cards collapse to a single line showing `p.X · italic question · ›`. Latest 1–2 stay expanded with the full V3Card treatment. A divider row `Latest · expanded` separates them.

Collapsed row: `padding: 8px 12px`, `border: 1px solid var(--paper-2)`, `border-left: 3px solid var(--accent)`, `border-radius: 8px`. Hover: slight background lift. Tap to expand.

### 4. Reading mode (Ambitious)

Toggled via top-right pill. When on:

- Top bar dims to 0.55 opacity.
- Margin column slides out to the right (opacity 0, `translateX(40px)`, 260ms).
- Book widens (`max-width 1100 → 1240`) and centers with more vertical air.
- Background shifts to an **ambient paper gradient**: `radial-gradient(ellipse 80% 60% at center 40%, oklch(96% 0.012 85), oklch(93% 0.015 80) 80%)`. Transition: 420ms `cubic-bezier(.2,.7,.2,1)`.
- **"Stave One · of five"** pacing label fades in at top, italic serif 12px, uppercase, `letter-spacing: 1.4px`.
- Page-turn arrows appear as faint circular buttons at left/right edges, `width: 48px`, `opacity: 0.5`.
- Thin progress hairline at the bottom edge: 3px, `background: var(--paper-2)`, foreground bar in `var(--accent)` at book progress %.
- Legend at bottom: `ASKED · NOTED · ENTITY` with color samples, 10.5px uppercase.
- **Note peek**: hovering a noted phrase shows a popover beneath the spread. `background: var(--paper-00)`, `border-left: 3px solid oklch(58% 0.1 55)`, `border-radius: 10px`, `padding: 12px 16px`, width 360px, shadow `0 20px 40px -12px rgba(28,24,18,.2)`. Shows the note body + "2 days ago" etc.
- Asked/noted/entity indicators stay visible on the page (not dimmed). These replace the sidebar as memory of prior activity.

The toggle pill: `padding: 5px 12px`, `border-radius: 999px`. Off state: `background: var(--paper-1)`, label "Reading mode". On state: `background: var(--ink-0)`, `color: var(--paper-00)`, label "✓ Reading".

### 5. Selection → Ask flow

Not yet mocked as an atomic state but implied by the design:
1. User selects text on the page
2. A small toolbar appears above the selection with `Ask` / `Note` / `Highlight` actions
3. Tapping Ask streams an answer into a new card in the margin
4. Scroll the margin to bring the new card into view

Toolbar visual: small pill group, dark background (`var(--ink-0)`), white text, ~32px tall. Appear/disappear animation is a fade + 4px slide up (180ms).

### 6. Chat open animation

See visualizer section "Chat open — transition animations" artboard `AN3` (V3 Inline).
- When Ask triggers, the highlighted phrase pulses (background flash).
- Cards flip in from the left edge with a slight stagger (first at 60ms, second at 200ms).
- Total duration: 520ms with smooth ease.

## Interactions & behavior

| Trigger | Effect |
|---|---|
| Highlight text | Selection toolbar appears |
| Tap Ask | Creates a new ask card; streams answer token-by-token |
| Tap Note | Creates a note card; user types body inline |
| Tap existing ask/note indicator on page | Scrolls/focuses the corresponding card in margin |
| Ask about a phrase that already has a card | Focus the existing card, open its follow-up composer. Do NOT create a duplicate. |
| Tap card in margin | Scrolls/flashes the anchor phrase on the page |
| Tap Reading mode pill | Toggles reading mode (420ms transition) |
| Hover note in reading mode | Note-peek popover appears after ~150ms |
| Arrow keys | Page turn (instant in v1) |
| Page turn | Reading cursor advances to the last sentence on the new spread |

**Edit/delete cards:** Only from a card-detail view. **This view is not yet designed** — flag for a follow-up pass before implementing delete/edit.

## State management

```ts
// Global / per-book
readingMode: boolean                    // localStorage: bookrag.reading-mode.{bookId}
cursor: { bookId, anchor }              // localStorage: bookrag.cursor.{bookId}
currentBookId: string                   // from URL /book/{bookId}

// Per-spread / local component
cards: Card[]                           // from backend (kuzudb)
visibleAnchors: Set<string>             // which p{n}.s{m} are on the current spread
selectedText: { range, anchor } | null  // selection toolbar state
streamingCardId: string | null          // for the typing cursor
```

## Data model

```ts
type Card = {
  id: string;                    // uuid
  bookId: string;
  anchor: string;                // "p12.s3" — sentence-level ID from ingestion
  quote: string;                 // exact text of the anchored span
  chapter: number;               // from EPUB spine
  kind: "ask" | "note";
  createdAt: ISO8601;
  updatedAt: ISO8601;
} & (
  | { kind: "ask"; question: string; answer: string; followups: { question: string; answer: string }[] }
  | { kind: "note"; body: string }
);

type ReadingCursor = {
  bookId: string;
  anchor: string;                // last sentence the user has read past
};
```

Confirm exact schema with the backend layer (CLAUDE.md).

## Design tokens

All tokens live in `tokens.css` (included). CSS variables; import once and reference:

**Paper & ink (neutrals):**
- `--paper-00`: pure page
- `--paper-0`: page tint (default background)
- `--paper-1`: soft chrome / toggle off
- `--paper-2`: borders / dividers
- `--paper-3`: stronger border / dashed lines
- `--ink-0`: primary text
- `--ink-1`: secondary text
- `--ink-2`: tertiary / icon
- `--ink-3`: quaternary / meta

**Accent (sage green):**
- `--accent`: primary accent (highlights, active pill)
- `--accent-ink`: accent-colored text on light
- `--accent-soft`: soft accent tint
- `--accent-softer`: softest accent tint

**Note accent (warm orange-brown):**
- `oklch(58% 0.1 55)` — note border, underline
- `oklch(30% 0.1 55)` — note header label text

**Type:**
- `--serif`: Lora — body text, pages, cards
- `--sans`: IBM Plex Sans — chrome, labels, buttons
- `--mono`: IBM Plex Mono — page numbers, codes

**Radii:**
- Pages: `3px` (book)
- Cards: `10px`
- Pills: `999px`
- Small chrome (e.g. collapsed rows): `8px`

**Shadows:**
- Book: `0 30px 70px -24px rgba(28,24,18,.2), 0 10px 20px -8px rgba(28,24,18,.08)`
- Card: `0 4px 12px -4px rgba(28,24,18,.08)`
- Note peek: `0 20px 40px -12px rgba(28,24,18,.2)`

**Motion:**
- Fast (hover, selection toolbar): 180ms ease
- Standard (pill toggle, card enter): 260–320ms ease
- Reading-mode transition: 420ms `cubic-bezier(.2,.7,.2,1)`
- Chat open: 520ms smooth ease

## Assets

No images or custom icons — all iconography uses the simple stroke-based `Icon` component in `icons.jsx` (see the prototype). Port these as simple SVG components in the target codebase: `IcSearch`, `IcBookmark`, `IcSpark`, `IcArrowL`, `IcArrowR`, `IcPlus`, `IcClose`, `IcChevron`, `IcCheck`, `IcLock`.

EPUB book content comes from the backend ingestion pipeline — the reader doesn't ship any sample books.

## Files in this handoff

- `README.md` — this file
- `Handoff Spec.html` — one-page decision spec (short form of this readme)
- `EPUB Visualizer v6.html` — all design artboards (states, overflow, reading mode, chat directions, spreads)
- `EPUB Ingestion Plan.html` — backend context (how EPUBs become the anchored corpus)
- `BookRAG Design System.html` — tokens, components, type
- `tokens.css` — CSS variable definitions (import as-is)
- `reader-*.jsx`, `components*.jsx`, `icons.jsx`, `design-canvas.jsx` — prototype source. Read for behavior/pattern reference; do NOT port literally.

## Build order

From the Handoff Spec — roughly 14 days of work:

1. **Reading surface** — paginated two-page spread with real EPUB content (~2d)
2. **Sentence anchors rendered** as `data-sid="p12.s3"` (~0.5d)
3. **Fog-of-war cursor** — dim/blur after cursor, advance on turn (~1d)
4. **V3 Inline margin column** — render cards keyed to visible anchors (~2d)
5. **Selection → Ask flow** — token-streamed answers (~2d)
6. **Notes** — same flow, body-only, no LLM (~1d)
7. **Card states** — streaming, long-answer, thread, off-screen, cross-page (~2d)
8. **O2 overflow** — collapse older cards to 1-liners (~1d)
9. **Reading mode (ambitious)** — toggle, ambient paper, note-peek (~1.5d)
10. **Card detail view** — edit + delete. **Design pass needed first** (~1d after design)

## Known gaps

- **Card detail view** not yet designed (step 10)
- **Virtual pagination engine** not prototyped — real engineering work, bites at step 1
- **Card-to-span connector** uses static SVGs in mocks; production needs DOM measurement + ResizeObserver
- **Mobile/touch** out of scope for v1; hover-peek has no touch fallback

## Questions for backend (CLAUDE.md)

- Is sentence ID `p{n}.s{m}` 0-indexed or 1-indexed?
- What API does the reader call to fetch chapters + anchors? (HTTP endpoint shape)
- Where do new cards get persisted? (Assumed kuzudb per CLAUDE.md)
- How does RAG retrieval surface answers — streaming endpoint? SSE? WebSocket?
