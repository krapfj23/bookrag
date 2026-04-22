# Slice R3 — Card states (S1–S7) + O2 overflow PRD

**Date:** 2026-04-22
**Parent:** ../../design_handoff_bookrag_reader/README.md

## Goal

Promote the R2 margin column from a single card shape to the full atomic card-state vocabulary (S1–S7) plus O2 collapse overflow, so a reader's annotations read like a hand-marked book instead of a flat list.

## User stories

- As a reader, I see a blinking cursor and a "gathering passages" skeleton while an ask is resolving, so I know the system is working before the first token lands.
- As a reader, a long answer stays inside its card with a scroll region and bottom fade, so one verbose response doesn't push everything else off-screen.
- As a reader, I can ask a follow-up question inside an existing ask card and watch the follow-up attach underneath with a dashed thread rule, so related turns stay grouped.
- As a reader, when a card's anchor is above my scroll or on the opposite page of the spread, the card's header tells me where to look and a colored edge bar / "Jump to anchor" CTA gets me there.
- As a reader, when a spread accumulates more than two cards, older ones collapse to a single summary line under a "Latest · expanded" divider, so I keep working context without losing the stack.

## Acceptance criteria

1. **S1 Empty**: when no cards match `visibleAnchors`, the margin renders the invitation card (sparkle badge, serif heading "Ask about what you're reading", three suggested-question bullets with mono numerals). (Carried over from R2; re-verified.)
2. **S2 Single + connector**: with exactly one card on the spread, a dashed SVG connector in `var(--accent)` at 0.6 opacity is rendered from the card's left edge to the anchored phrase's bounding box on the page. The connector repositions on window resize and page turn. With ≥2 cards on the spread, no connector is rendered (documented fallback).
3. **S3 Streaming**: while an ask is awaiting its first token, a skeleton card is rendered in the card's place with label "THINKING · gathering 3 more passages" and two shimmering placeholder lines. When the first chunk arrives, the skeleton is replaced by the real card. While `answer` is still growing, a 6×14px `var(--ink-2)` block renders at the end of the answer text with `animation: blink 1s infinite`. The cursor disappears when streaming completes.
4. **S4 Long answer**: an ask card whose rendered answer height would exceed 220px constrains its answer region to `max-height: 220px; overflow: auto`, and a bottom fade gradient (transparent → `var(--paper-00)`) overlays the final ~24px of the region. Cards under 220px render without the fade.
5. **S5 Thread**: an expanded ask card shows a follow-up composer (single-line input, placeholder "Ask a follow-up…") pinned below its answer. Submitting the composer appends an entry to `card.followups` and renders it beneath the primary answer, indented 14px with a `1px dashed var(--paper-3)` left border, preceded by a "FOLLOW-UP" header label (9.5px uppercase, `var(--accent-ink)`). Follow-up answers stream via the same R2 chunker. Duplicate-ask on an anchor that already has an ask card focuses that card and focuses its follow-up composer (supersedes the R2 focus-only behavior).
6. **S6 Off-screen anchor**: a card whose anchor `sid` is on the current spread but whose anchored phrase is outside the margin column's visible scroll (detected via `IntersectionObserver` on anchor elements) prefixes its header with `↑ SCROLL UP ·` (or `↓ SCROLL DOWN ·` when below the viewport), renders a 3px vertical bar in `var(--accent)` on the book spread's right edge aligned to the anchor's vertical position, and shows a "Jump to anchor on this page" CTA below the card (`var(--accent-softer)` background, dashed `var(--accent)` border). Clicking the CTA scrolls the page to the anchor and flashes it.
7. **S7 Cross-page**: a card whose anchor `sid` resolves to the opposite page of the current two-page spread prefixes its header with `← FROM p. {n} ·` (or `→ FROM p. {n} ·` for right→left), where `{n}` is the 1-indexed folio number of the anchor's page. The rest of the card renders identically to S2/S4/S5 as applicable.
8. **O2 collapse threshold**: when `visibleCards.length > 2`, the latest 2 (by `updatedAt`) render expanded; all older cards render as collapsed one-line rows (`p.{n} · {italic question or note first line} · ›`, 8px×12px padding, 8px radius, `border-left: 3px solid var(--accent)` for ask / note orange for notes).
9. **O2 divider**: a divider row with label "Latest · expanded" (9.5px uppercase, `letter-spacing: 1.3px`, `var(--ink-3)`, flanked by 1px `var(--paper-2)` rules) is rendered between the collapsed stack and the expanded tail, and only when at least one card is collapsed.
10. **O2 expand on click**: clicking a collapsed row expands that card inline (replaces the row with the full card treatment) and collapses whichever expanded card is now oldest, keeping at most 2 expanded at a time. Hover on a collapsed row applies a subtle background lift.
11. A Playwright spec `frontend/e2e/slice-R3-card-states-and-overflow.spec.ts` exercises: S1 invitation visible with zero cards; S2 connector SVG present with exactly one card; S3 skeleton then blinking cursor during an ask; S4 scrollable answer region + fade with a long seeded answer; S5 follow-up composer submits and appends a threaded reply; S6 `↑ SCROLL UP` prefix + edge bar + jump CTA when the anchor is scrolled out of view; S7 `← FROM p.` prefix when the anchor is on the opposite page; O2 collapse behavior with 3+ seeded cards, including the "Latest · expanded" divider and expand-on-click.

## UI scope

**In scope (R3):**
- `AskCard` / `NoteCard` extended for S3/S4/S5/S6/S7 affordances.
- New `CollapsedCardRow`, `LatestExpandedDivider`, `FollowupComposer`, `AnchorConnector` (SVG), `AnchorEdgeBar`, `JumpToAnchorCTA`, `SkeletonAskCard`, `BlinkingCursor` components.
- `useCards` extended with `appendFollowup(cardId, question, answer)` and a `loading` flag per ask card.
- `useVisibleAnchors` / `MarginColumn` extended with `IntersectionObserver` wiring for S6 and page-side detection for S7.
- Overflow policy lives in `MarginColumn`: partition visible cards into `{ collapsed, expanded }` and render divider.

**Out of scope:** reading mode toggle, ambient paper gradient, progress hairline, pacing label, legend, note-peek popover (all R4); card detail / edit / delete (blocked on design); entity dotted underlines; chat-open flip-in animation (AN3); server-side persistence.

## Backend scope

None. Confirmed: R3 is pure frontend polish on top of R2's `POST /books/{book_id}/query` contract. The follow-up composer reuses the same endpoint with the same `max_chapter` fog-of-war bound.

## Data contracts

```ts
interface BaseCard {
  id: string;
  bookId: string;
  anchor: string;                // "p{n}.s{m}"
  quote: string;
  chapter: number;
  createdAt: string;
  updatedAt: string;
}

interface AskCard extends BaseCard {
  kind: "ask";
  question: string;
  answer: string;
  followups: { question: string; answer: string }[]; // populated in R3
  loading?: boolean;              // true from ask-dispatch until first chunk arrives (drives S3 skeleton)
  streaming?: boolean;            // true while chunker is still running (drives S3 blinking cursor)
  followupLoading?: boolean;      // true while a followup is resolving (drives per-followup cursor)
}

interface NoteCard extends BaseCard {
  kind: "note";
  body: string;
}

type Card = AskCard | NoteCard;

// localStorage key remains `bookrag.cards.{bookId}`; CardStore.version stays at 1.
// `loading`, `streaming`, `followupLoading` are runtime-only and MUST be stripped
// before persisting (they never round-trip through localStorage).
```

Schema stays backward-compatible with R2: `followups` already existed and defaulted to `[]`; transient flags are optional.

## Out of scope

- Reading mode, ambient paper gradient, note-peek, progress hairline, legend.
- Card detail / edit / delete.
- Server-side card persistence.
- Real SSE/WebSocket streaming.
- Entity dotted underlines.
- Connector SVG for multi-card spreads (explicit fallback: single-card only).
- Mobile/touch behavior.

## Open questions

- Connector geometry with >1 card is deferred; if user testing shows the single-card connector feels arbitrary, consider dropping S2's connector entirely rather than shipping inconsistent behavior.
- S3 skeleton label hardcodes "gathering 3 more passages" — confirm whether the "3" should reflect a real retrieval count from the backend or stay as flavor copy (recommend flavor copy for R3; wire real count when/if `/query` returns retrieval metadata).
- S6 edge-bar color matches the card's accent (ask-green / note-orange); confirm mixed stacks render one bar per off-screen card rather than a merged bar.
