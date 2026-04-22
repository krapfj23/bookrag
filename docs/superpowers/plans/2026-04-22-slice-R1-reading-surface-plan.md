# Slice R1 — Reading surface + sentence anchors — Implementation Plan

**Date:** 2026-04-22
**Spec:** `docs/superpowers/specs/2026-04-22-slice-R1-reading-surface.md`
**Design handoff:** `design_handoff_bookrag_reader/`

## Conventions

- Backend tests: `source .venv/bin/activate && pytest tests/<name>.py -v --tb=short`.
- Frontend unit: from `frontend/`, `npm test -- --run <path>`.
- Playwright: from `frontend/`, `npx playwright test frontend/e2e/slice-R1-reading-surface.spec.ts`.
- Every task ends with `git commit -m "Slice R1 T<N>: <what>"`. No co-authored-by trailers.
- Existing frontend route `/books/:bookId/read/:chapterNum` is retained (the spec's `/book/{bookId}` + `#chapter=` wording maps to the same semantics; AC4 explicitly says "re-uses existing `BookReadingRedirect`").

---

## Task 1 — Backend: add `paragraphs_anchored` from BookNLP `.tokens`

**Goal:** `GET /books/{book_id}/chapters/{n}` emits `paragraphs_anchored` + `anchors_fallback` while preserving existing fields. Anchors derive from `.tokens` TSV when reconcilable; else regex fallback.

**Create:** `api/loaders/sentence_anchors.py`
**Modify:** `api/loaders/book_data.py` (extend `Chapter` model + `load_chapter`)
**Modify:** `api/routes/chapters.py` (no shape change — model picks up new fields)
**Test:** `tests/test_sentence_anchors.py`

### 1.1 Write failing test

`tests/test_sentence_anchors.py`:

```python
"""Tests for sentence-anchored chapter loader (Slice R1, AC 1–3)."""
from __future__ import annotations

from pathlib import Path

from api.loaders.book_data import load_chapter
from api.loaders.sentence_anchors import (
    build_paragraphs_anchored,
    regex_fallback_paragraphs,
)
from models.pipeline_state import PipelineState, save_state


CH1 = (
    "Marley was dead, to begin with. There is no doubt about that.\n\n"
    "Scrooge knew he was dead. Of course he did. He was his partner."
)


def _ready(processed: Path, book_id: str) -> Path:
    book = processed / book_id
    (book / "raw" / "chapters").mkdir(parents=True, exist_ok=True)
    (book / "raw" / "chapters" / "chapter_01.txt").write_text(CH1, encoding="utf-8")
    s = PipelineState.new(book_id, ["parse_epub", "validate"])
    s.status = "complete"
    s.ready_for_query = True
    save_state(s, book / "pipeline_state.json")
    return book


def test_regex_fallback_produces_anchored_paragraphs(tmp_path):
    paragraphs = [
        "Marley was dead, to begin with. There is no doubt about that.",
        "Scrooge knew he was dead. Of course he did. He was his partner.",
    ]
    anchored = regex_fallback_paragraphs(paragraphs)
    assert len(anchored) == 2
    assert [s.sid for s in anchored[0].sentences] == ["p1.s1", "p1.s2"]
    assert anchored[0].sentences[0].text.startswith("Marley was dead")
    assert [s.sid for s in anchored[1].sentences] == ["p2.s1", "p2.s2", "p2.s3"]


def test_load_chapter_includes_paragraphs_anchored_and_fallback_flag(tmp_path):
    _ready(tmp_path, "carol")
    chapter = load_chapter("carol", 1, tmp_path)
    assert chapter is not None
    # Existing fields unchanged.
    assert chapter.num == 1
    assert chapter.has_prev is False
    assert chapter.total_chapters == 1
    assert len(chapter.paragraphs) == 2
    # New fields.
    assert chapter.anchors_fallback is True  # no BookNLP run → fallback
    assert len(chapter.paragraphs_anchored) == 2
    first = chapter.paragraphs_anchored[0]
    assert first.paragraph_idx == 1
    assert first.sentences[0].sid == "p1.s1"
    assert first.sentences[1].sid == "p1.s2"
    second = chapter.paragraphs_anchored[1]
    assert second.paragraph_idx == 2
    assert [s.sid for s in second.sentences] == ["p2.s1", "p2.s2", "p2.s3"]


def test_build_paragraphs_anchored_from_tokens(tmp_path):
    # Simulated .tokens rows: paragraph_ID + sentence_ID + byte offsets.
    tokens = [
        {"paragraph_ID": 0, "sentence_ID": 0, "word": "Marley",   "byte_onset": 0,  "byte_offset": 6},
        {"paragraph_ID": 0, "sentence_ID": 0, "word": "was",      "byte_onset": 7,  "byte_offset": 10},
        {"paragraph_ID": 0, "sentence_ID": 0, "word": "dead.",    "byte_onset": 11, "byte_offset": 16},
        {"paragraph_ID": 0, "sentence_ID": 1, "word": "No",       "byte_onset": 17, "byte_offset": 19},
        {"paragraph_ID": 0, "sentence_ID": 1, "word": "doubt.",   "byte_onset": 20, "byte_offset": 26},
        {"paragraph_ID": 1, "sentence_ID": 2, "word": "Scrooge",  "byte_onset": 28, "byte_offset": 35},
        {"paragraph_ID": 1, "sentence_ID": 2, "word": "knew.",    "byte_onset": 36, "byte_offset": 41},
    ]
    text = "Marley was dead. No doubt.\n\nScrooge knew."
    anchored, ok = build_paragraphs_anchored(text, tokens, chapter_start=0, chapter_end=len(text))
    assert ok is True
    assert [p.paragraph_idx for p in anchored] == [1, 2]
    assert [s.sid for s in anchored[0].sentences] == ["p1.s1", "p1.s2"]
    assert anchored[0].sentences[0].text.startswith("Marley was dead")
    assert [s.sid for s in anchored[1].sentences] == ["p2.s1"]
```

### 1.2 Run the test (expect failure)

```bash
source .venv/bin/activate && pytest tests/test_sentence_anchors.py -v --tb=short
```

Expected: `ModuleNotFoundError: No module named 'api.loaders.sentence_anchors'` and `AttributeError: 'Chapter' object has no attribute 'anchors_fallback'`.

### 1.3 Implement

**Create `api/loaders/sentence_anchors.py`:**

```python
"""Derive sentence-anchored paragraphs for a chapter.

Strategy:
  1. If a BookNLP .tokens file exists for the book and its byte offsets
     reconcile with the chapter's cleaned text, group tokens by
     paragraph_ID then sentence_ID and emit p{n}.s{m} ids.
  2. Otherwise, split each paragraph string on a sentence-ending regex
     and emit p{n}.s{m} ids; set anchors_fallback=True.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from pydantic import BaseModel


class AnchoredSentence(BaseModel):
    sid: str
    text: str


class AnchoredParagraph(BaseModel):
    paragraph_idx: int
    sentences: list[AnchoredSentence]


_SENT_SPLIT_RE = re.compile(r"(?<=[.!?])[\"')\]]*\s+(?=[A-Z\"'(\[])")


def regex_fallback_paragraphs(paragraphs: list[str]) -> list[AnchoredParagraph]:
    out: list[AnchoredParagraph] = []
    for p_idx, para in enumerate(paragraphs, start=1):
        parts = [s.strip() for s in _SENT_SPLIT_RE.split(para) if s.strip()]
        if not parts:
            parts = [para.strip()]
        sents = [
            AnchoredSentence(sid=f"p{p_idx}.s{s_idx}", text=t)
            for s_idx, t in enumerate(parts, start=1)
        ]
        out.append(AnchoredParagraph(paragraph_idx=p_idx, sentences=sents))
    return out


def build_paragraphs_anchored(
    chapter_text: str,
    token_rows: Iterable[dict],
    chapter_start: int,
    chapter_end: int,
) -> tuple[list[AnchoredParagraph], bool]:
    """Return (anchored, ok). ok=False means caller should fall back."""
    # Filter tokens whose byte range lies inside the chapter slice.
    rows: list[dict] = []
    for r in token_rows:
        try:
            bo = int(r.get("byte_onset", r.get("start_char", -1)))
            be = int(r.get("byte_offset", r.get("end_char", -1)))
        except (TypeError, ValueError):
            continue
        if bo < 0 or be < 0:
            continue
        if bo >= chapter_start and be <= chapter_end:
            rows.append({**r, "_bo": bo, "_be": be})

    if not rows:
        return [], False

    # Group by paragraph_ID (preserve order of first appearance).
    para_order: list[int] = []
    by_para: dict[int, list[dict]] = {}
    for r in rows:
        try:
            pid = int(r.get("paragraph_ID", r.get("paragraph_id", -1)))
        except (TypeError, ValueError):
            return [], False
        if pid < 0:
            return [], False
        if pid not in by_para:
            by_para[pid] = []
            para_order.append(pid)
        by_para[pid].append(r)

    anchored: list[AnchoredParagraph] = []
    for p_idx, pid in enumerate(para_order, start=1):
        # Group this paragraph's tokens by sentence_ID preserving order.
        sent_order: list[int] = []
        by_sent: dict[int, list[dict]] = {}
        for r in by_para[pid]:
            try:
                sid = int(r.get("sentence_ID", r.get("sentence_id", -1)))
            except (TypeError, ValueError):
                return [], False
            if sid < 0:
                return [], False
            if sid not in by_sent:
                by_sent[sid] = []
                sent_order.append(sid)
            by_sent[sid].append(r)
        sentences: list[AnchoredSentence] = []
        for s_idx, sid in enumerate(sent_order, start=1):
            toks = by_sent[sid]
            s_bo = min(t["_bo"] for t in toks) - chapter_start
            s_be = max(t["_be"] for t in toks) - chapter_start
            s_bo = max(0, s_bo)
            s_be = min(len(chapter_text), s_be)
            text = chapter_text[s_bo:s_be].strip()
            if not text:
                # Could not slice text back — signal fallback.
                return [], False
            sentences.append(AnchoredSentence(sid=f"p{p_idx}.s{s_idx}", text=text))
        if sentences:
            anchored.append(AnchoredParagraph(paragraph_idx=p_idx, sentences=sentences))

    if not anchored:
        return [], False
    return anchored, True


def find_chapter_offsets(full_text: str, chapter_text: str) -> tuple[int, int] | None:
    """Locate chapter_text inside full_text. Returns (start, end) bytes or None."""
    start = full_text.find(chapter_text)
    if start < 0:
        return None
    return start, start + len(chapter_text)


def load_tokens_for_book(book_id: str, processed_dir: Path) -> list[dict] | None:
    booknlp_dir = processed_dir / book_id / "booknlp"
    if not booknlp_dir.exists():
        return None
    # The BookNLP runner writes {book_id}.tokens; see booknlp_runner.run_booknlp.
    candidate = booknlp_dir / f"{book_id}.tokens"
    if not candidate.exists():
        matches = list(booknlp_dir.glob("*.tokens"))
        if not matches:
            return None
        candidate = matches[0]
    from pipeline.tsv_utils import read_tsv
    return read_tsv(candidate)


def load_cleaned_full_text(book_id: str, processed_dir: Path) -> str | None:
    """Reconstruct cleaned full text by concatenating chapter_*.txt."""
    chapters_dir = processed_dir / book_id / "raw" / "chapters"
    if not chapters_dir.exists():
        return None
    parts: list[str] = []
    for p in sorted(chapters_dir.glob("chapter_*.txt")):
        parts.append(p.read_text(encoding="utf-8"))
    return "\n\n".join(parts) if parts else None
```

**Modify `api/loaders/book_data.py`:**

Add imports and extend `Chapter`, `load_chapter`:

```python
# near top
from api.loaders.sentence_anchors import (
    AnchoredParagraph,
    build_paragraphs_anchored,
    find_chapter_offsets,
    load_cleaned_full_text,
    load_tokens_for_book,
    regex_fallback_paragraphs,
)

# Replace the Chapter model
class Chapter(BaseModel):
    num: int
    title: str
    paragraphs: list[str]
    paragraphs_anchored: list[AnchoredParagraph] = []
    anchors_fallback: bool = True
    has_prev: bool
    has_next: bool
    total_chapters: int
```

Extend `load_chapter` to compute anchors:

```python
def load_chapter(book_id: str, n: int, processed_dir: Path) -> Chapter | None:
    files = list_chapter_files(book_id, processed_dir)
    if not files:
        return None
    if n < 1 or n > len(files):
        return None
    raw_text = files[n - 1].read_text(encoding="utf-8")
    paragraphs = [p.strip() for p in raw_text.split("\n\n") if p.strip()]
    title = _derive_chapter_title(raw_text, n)

    anchored: list[AnchoredParagraph] = []
    fallback = True
    tokens = load_tokens_for_book(book_id, processed_dir)
    full_text = load_cleaned_full_text(book_id, processed_dir)
    if tokens and full_text:
        offsets = find_chapter_offsets(full_text, raw_text)
        if offsets is not None:
            start, end = offsets
            anchored, ok = build_paragraphs_anchored(raw_text, tokens, start, end)
            if ok:
                fallback = False
    if fallback:
        anchored = regex_fallback_paragraphs(paragraphs)

    return Chapter(
        num=n,
        title=title,
        paragraphs=paragraphs,
        paragraphs_anchored=anchored,
        anchors_fallback=fallback,
        has_prev=n > 1,
        has_next=n < len(files),
        total_chapters=len(files),
    )
```

### 1.4 Run the test (expect pass)

```bash
source .venv/bin/activate && pytest tests/test_sentence_anchors.py -v --tb=short
```

Expected: all 3 tests pass. Also run the existing chapters endpoint tests to confirm no regression:

```bash
source .venv/bin/activate && pytest tests/test_chapters_endpoints.py -v --tb=short
```

Expected: existing tests pass (new fields default to `[]` and `True` when BookNLP output is absent).

### 1.5 Commit

```bash
git add api/loaders/sentence_anchors.py api/loaders/book_data.py tests/test_sentence_anchors.py
git commit -m "Slice R1 T1: add paragraphs_anchored + anchors_fallback to chapter endpoint"
```

---

## Task 2 — Frontend: import design tokens + add API types for anchors

**Goal:** Bring anchor types into the frontend API client. Ensure `frontend/src/styles/tokens.css` equals `design_handoff_bookrag_reader/tokens.css` verbatim. (It is already imported in existing components per `frontend/src/main.tsx`.)

**Modify:** `frontend/src/lib/api.ts`
**Modify:** `frontend/src/styles/tokens.css` (sync to handoff)
**Test:** `frontend/src/lib/api.anchors.test.ts`

### 2.1 Failing test

`frontend/src/lib/api.anchors.test.ts`:

```ts
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { fetchChapter, type Chapter } from "./api";

const BOOK = "carol";
const URL = "http://localhost:8000/books/carol/chapters/1";

describe("fetchChapter — anchored paragraphs", () => {
  const realFetch = global.fetch;
  beforeEach(() => {
    global.fetch = vi.fn(async () =>
      new Response(
        JSON.stringify({
          num: 1,
          title: "Marley's Ghost",
          paragraphs: ["Marley was dead. No doubt."],
          paragraphs_anchored: [
            {
              paragraph_idx: 1,
              sentences: [
                { sid: "p1.s1", text: "Marley was dead." },
                { sid: "p1.s2", text: "No doubt." },
              ],
            },
          ],
          anchors_fallback: false,
          has_prev: false,
          has_next: false,
          total_chapters: 1,
        }),
        { status: 200, headers: { "Content-Type": "application/json" } },
      ),
    ) as typeof fetch;
  });
  afterEach(() => {
    global.fetch = realFetch;
  });

  it("parses paragraphs_anchored + anchors_fallback", async () => {
    const ch: Chapter = await fetchChapter(BOOK, 1);
    expect(ch.anchors_fallback).toBe(false);
    expect(ch.paragraphs_anchored).toHaveLength(1);
    const p1 = ch.paragraphs_anchored[0];
    expect(p1.paragraph_idx).toBe(1);
    expect(p1.sentences.map((s) => s.sid)).toEqual(["p1.s1", "p1.s2"]);
    expect(p1.sentences[0].text).toBe("Marley was dead.");
    void URL;
  });
});
```

### 2.2 Run (expect failure)

```bash
cd frontend && npm test -- --run src/lib/api.anchors.test.ts
```

Expected: TS error — `Property 'paragraphs_anchored' does not exist on type 'Chapter'`.

### 2.3 Implement

Modify `frontend/src/lib/api.ts` — extend the `Chapter` type and add anchor types:

```ts
export type AnchoredSentence = { sid: string; text: string };
export type AnchoredParagraph = {
  paragraph_idx: number;
  sentences: AnchoredSentence[];
};

export type Chapter = {
  num: number;
  title: string;
  paragraphs: string[];
  paragraphs_anchored: AnchoredParagraph[];
  anchors_fallback: boolean;
  has_prev: boolean;
  has_next: boolean;
  total_chapters: number;
};
```

Sync `frontend/src/styles/tokens.css` with `design_handoff_bookrag_reader/tokens.css` verbatim (copy contents).

### 2.4 Run (expect pass)

```bash
cd frontend && npm test -- --run src/lib/api.anchors.test.ts
```

Expected: 1 passed.

### 2.5 Commit

```bash
git add frontend/src/lib/api.ts frontend/src/lib/api.anchors.test.ts frontend/src/styles/tokens.css
git commit -m "Slice R1 T2: expose AnchoredParagraph types and sync design tokens"
```

---

## Task 3 — Sentence/Paragraph render primitives (`data-sid`)

**Goal:** Lightweight components that render `<p><span data-sid=...>...</span></p>` with an opacity/blur state for fog.

**Create:** `frontend/src/components/reader/Sentence.tsx`
**Create:** `frontend/src/components/reader/Paragraph.tsx`
**Create:** `frontend/src/components/reader/Sentence.test.tsx`

### 3.1 Failing test

`frontend/src/components/reader/Sentence.test.tsx`:

```tsx
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { Sentence } from "./Sentence";
import { Paragraph } from "./Paragraph";

describe("Sentence", () => {
  it("emits data-sid and text", () => {
    render(<Sentence sid="p1.s2" text="Hello." fogged={false} />);
    const el = screen.getByText("Hello.");
    expect(el.getAttribute("data-sid")).toBe("p1.s2");
  });

  it("applies fog styling when fogged", () => {
    render(<Sentence sid="p1.s2" text="Hello." fogged={true} />);
    const el = screen.getByText("Hello.");
    const style = el.getAttribute("style") ?? "";
    expect(style).toMatch(/opacity/);
    expect(style).toMatch(/blur/);
  });
});

describe("Paragraph", () => {
  it("renders each sentence with data-sid, drop cap flag on first", () => {
    const sentences = [
      { sid: "p1.s1", text: "Alpha." },
      { sid: "p1.s2", text: "Bravo." },
    ];
    render(
      <Paragraph
        paragraphIdx={1}
        sentences={sentences}
        fogStartSid={null}
        dropCap={true}
      />,
    );
    expect(document.querySelector('[data-sid="p1.s1"]')).not.toBeNull();
    expect(document.querySelector('[data-sid="p1.s2"]')).not.toBeNull();
    expect(document.querySelector(".rr-dropcap")).not.toBeNull();
  });
});
```

### 3.2 Run (expect failure)

```bash
cd frontend && npm test -- --run src/components/reader/Sentence.test.tsx
```

Expected: `Failed to resolve import "./Sentence"`.

### 3.3 Implement

`frontend/src/components/reader/Sentence.tsx`:

```tsx
import type { CSSProperties } from "react";

export function Sentence({
  sid,
  text,
  fogged,
}: {
  sid: string;
  text: string;
  fogged: boolean;
}) {
  const style: CSSProperties = fogged
    ? { opacity: 0.3, filter: "blur(2.2px)", transition: "opacity 180ms ease, filter 180ms ease" }
    : { opacity: 1, filter: "blur(0)", transition: "opacity 180ms ease, filter 180ms ease" };
  return (
    <span data-sid={sid} style={style}>
      {text}
    </span>
  );
}
```

`frontend/src/components/reader/Paragraph.tsx`:

```tsx
import { Sentence } from "./Sentence";
import type { AnchoredSentence } from "../../lib/api";
import { compareSid } from "../../lib/reader/sidCompare";

export function Paragraph({
  paragraphIdx,
  sentences,
  fogStartSid,
  dropCap,
}: {
  paragraphIdx: number;
  sentences: AnchoredSentence[];
  fogStartSid: string | null;
  dropCap: boolean;
}) {
  return (
    <p
      data-paragraph-idx={paragraphIdx}
      className={dropCap ? "rr-para rr-dropcap" : "rr-para"}
      style={{ margin: "0 0 0.9em", textAlign: "justify", hyphens: "auto" }}
    >
      {sentences.map((s, i) => {
        const fogged = fogStartSid !== null && compareSid(s.sid, fogStartSid) > 0;
        return (
          <>
            <Sentence key={s.sid} sid={s.sid} text={s.text} fogged={fogged} />
            {i < sentences.length - 1 ? " " : ""}
          </>
        );
      })}
    </p>
  );
}
```

Also create `frontend/src/lib/reader/sidCompare.ts`:

```ts
export function parseSid(sid: string): [number, number] {
  const m = /^p(\d+)\.s(\d+)$/.exec(sid);
  if (!m) return [0, 0];
  return [Number.parseInt(m[1], 10), Number.parseInt(m[2], 10)];
}

export function compareSid(a: string, b: string): number {
  const [pa, sa] = parseSid(a);
  const [pb, sb] = parseSid(b);
  if (pa !== pb) return pa - pb;
  return sa - sb;
}
```

### 3.4 Run (expect pass)

```bash
cd frontend && npm test -- --run src/components/reader/Sentence.test.tsx
```

Expected: 3 passed.

### 3.5 Commit

```bash
git add frontend/src/components/reader/Sentence.tsx frontend/src/components/reader/Paragraph.tsx frontend/src/components/reader/Sentence.test.tsx frontend/src/lib/reader/sidCompare.ts
git commit -m "Slice R1 T3: Sentence and Paragraph primitives with data-sid"
```

---

## Task 4 — Client-side DOM paginator utility

**Goal:** Pure function that takes `AnchoredParagraph[]` and a target page box (width/height + CSS), chunks paragraphs into spreads (2 pages per spread) such that no sentence is split across pages. For R1, we split at **paragraph** granularity when a paragraph fits; when a paragraph overflows a single page, we split at sentence granularity. Uses an offscreen measuring div.

**Create:** `frontend/src/lib/reader/paginator.ts`
**Create:** `frontend/src/lib/reader/paginator.test.ts`

### 4.1 Failing test

`frontend/src/lib/reader/paginator.test.ts`:

```ts
/**
 * @vitest-environment jsdom
 */
import { describe, it, expect } from "vitest";
import { paginate, type Spread } from "./paginator";
import type { AnchoredParagraph } from "../api";

function para(idx: number, n: number): AnchoredParagraph {
  return {
    paragraph_idx: idx,
    sentences: Array.from({ length: n }, (_, i) => ({
      sid: `p${idx}.s${i + 1}`,
      text: `Sentence ${i + 1} of paragraph ${idx}.`,
    })),
  };
}

describe("paginate", () => {
  it("returns at least one spread and never splits a sentence", () => {
    const paragraphs: AnchoredParagraph[] = [
      para(1, 3),
      para(2, 2),
      para(3, 4),
    ];
    const spreads: Spread[] = paginate(paragraphs, {
      pageWidth: 360,
      pageHeight: 520,
      paddingPx: 48,
      fontPx: 15,
      lineHeight: 1.72,
    });
    expect(spreads.length).toBeGreaterThanOrEqual(1);
    const seen = new Set<string>();
    for (const sp of spreads) {
      for (const page of [sp.left, sp.right]) {
        for (const p of page) {
          for (const s of p.sentences) {
            expect(seen.has(s.sid)).toBe(false);
            seen.add(s.sid);
          }
        }
      }
    }
    // Every sentence appears exactly once.
    expect(seen.size).toBe(3 + 2 + 4);
  });

  it("produces spreads with last visible sid available", () => {
    const spreads = paginate([para(1, 2)], {
      pageWidth: 360,
      pageHeight: 520,
      paddingPx: 48,
      fontPx: 15,
      lineHeight: 1.72,
    });
    expect(spreads[0].lastSid).toBe("p1.s2");
  });
});
```

### 4.2 Run (expect failure)

```bash
cd frontend && npm test -- --run src/lib/reader/paginator.test.ts
```

Expected: `Failed to resolve import "./paginator"`.

### 4.3 Implement

`frontend/src/lib/reader/paginator.ts`:

```ts
import type { AnchoredParagraph, AnchoredSentence } from "../api";

export type PaginatorBox = {
  pageWidth: number;
  pageHeight: number;
  paddingPx: number;
  fontPx: number;
  lineHeight: number;
};

export type PageParagraph = {
  paragraph_idx: number;
  sentences: AnchoredSentence[];
  isContinuation?: boolean;
};

export type Page = PageParagraph[];

export type Spread = {
  index: number;
  left: Page;
  right: Page;
  lastSid: string;
  firstSid: string;
};

// Measurement: create a hidden element sized to the inner page box, append
// candidate paragraphs, measure scrollHeight. If scrollHeight <= innerHeight,
// the paragraph fits; else the last-added paragraph overflows.
function makeMeasurer(box: PaginatorBox): {
  el: HTMLDivElement;
  inner: HTMLDivElement;
  innerHeight: number;
  cleanup: () => void;
} {
  const el = document.createElement("div");
  el.style.position = "absolute";
  el.style.left = "-99999px";
  el.style.top = "0";
  el.style.width = `${box.pageWidth}px`;
  el.style.height = `${box.pageHeight}px`;
  el.style.padding = `${box.paddingPx}px`;
  el.style.boxSizing = "border-box";
  el.style.fontFamily = "var(--serif, Lora, serif)";
  el.style.fontSize = `${box.fontPx}px`;
  el.style.lineHeight = String(box.lineHeight);
  el.style.textAlign = "justify";
  const inner = document.createElement("div");
  inner.style.width = "100%";
  inner.style.height = "auto";
  el.appendChild(inner);
  document.body.appendChild(el);
  return {
    el,
    inner,
    innerHeight: box.pageHeight - box.paddingPx * 2,
    cleanup: () => el.remove(),
  };
}

function paragraphNode(p: PageParagraph): HTMLParagraphElement {
  const node = document.createElement("p");
  node.style.margin = "0 0 0.9em";
  node.style.hyphens = "auto";
  for (let i = 0; i < p.sentences.length; i++) {
    const span = document.createElement("span");
    span.setAttribute("data-sid", p.sentences[i].sid);
    span.textContent = p.sentences[i].text + (i < p.sentences.length - 1 ? " " : "");
    node.appendChild(span);
  }
  return node;
}

function packPage(
  remaining: PageParagraph[],
  inner: HTMLDivElement,
  innerHeight: number,
): { fitted: PageParagraph[]; leftover: PageParagraph[] } {
  const fitted: PageParagraph[] = [];
  inner.innerHTML = "";
  while (remaining.length) {
    const p = remaining[0];
    const node = paragraphNode(p);
    inner.appendChild(node);
    if (inner.scrollHeight <= innerHeight) {
      fitted.push(p);
      remaining.shift();
      continue;
    }
    // Does not fit whole. Try splitting at sentence boundary.
    inner.removeChild(node);
    const splitFit: AnchoredSentence[] = [];
    const splitRest: AnchoredSentence[] = [...p.sentences];
    const partialNode = document.createElement("p");
    partialNode.style.margin = "0 0 0.9em";
    inner.appendChild(partialNode);
    while (splitRest.length) {
      const s = splitRest[0];
      const span = document.createElement("span");
      span.setAttribute("data-sid", s.sid);
      span.textContent = s.text + " ";
      partialNode.appendChild(span);
      if (inner.scrollHeight <= innerHeight) {
        splitFit.push(s);
        splitRest.shift();
      } else {
        partialNode.removeChild(span);
        break;
      }
    }
    if (splitFit.length > 0) {
      fitted.push({
        paragraph_idx: p.paragraph_idx,
        sentences: splitFit,
        isContinuation: p.isContinuation ?? false,
      });
    }
    if (splitRest.length > 0) {
      // Put back the rest as a continuation of the same paragraph.
      remaining[0] = {
        paragraph_idx: p.paragraph_idx,
        sentences: splitRest,
        isContinuation: true,
      };
    } else {
      remaining.shift();
    }
    break;
  }
  return { fitted, leftover: remaining };
}

export function paginate(
  paragraphs: AnchoredParagraph[],
  box: PaginatorBox,
): Spread[] {
  const { inner, innerHeight, cleanup } = makeMeasurer(box);
  try {
    const queue: PageParagraph[] = paragraphs.map((p) => ({
      paragraph_idx: p.paragraph_idx,
      sentences: [...p.sentences],
    }));
    const spreads: Spread[] = [];
    let idx = 0;
    // Safety cap: at most 1 spread per sentence (impossible to exceed).
    const totalSentences = paragraphs.reduce((n, p) => n + p.sentences.length, 0);
    const maxSpreads = Math.max(1, totalSentences);
    while (queue.length && spreads.length < maxSpreads) {
      const leftPack = packPage(queue, inner, innerHeight);
      const left = leftPack.fitted;
      let right: PageParagraph[] = [];
      if (leftPack.leftover.length) {
        const rightPack = packPage(leftPack.leftover, inner, innerHeight);
        right = rightPack.fitted;
      }
      const pageParas = [...left, ...right];
      if (pageParas.length === 0) break;
      const flatSids = pageParas.flatMap((p) => p.sentences.map((s) => s.sid));
      spreads.push({
        index: idx++,
        left,
        right,
        firstSid: flatSids[0],
        lastSid: flatSids[flatSids.length - 1],
      });
    }
    if (spreads.length === 0) {
      // Fallback: one spread with everything left on the left page.
      const pageParas = paragraphs.map((p) => ({
        paragraph_idx: p.paragraph_idx,
        sentences: [...p.sentences],
      }));
      const flatSids = pageParas.flatMap((p) => p.sentences.map((s) => s.sid));
      spreads.push({
        index: 0,
        left: pageParas,
        right: [],
        firstSid: flatSids[0] ?? "p1.s1",
        lastSid: flatSids[flatSids.length - 1] ?? "p1.s1",
      });
    }
    return spreads;
  } finally {
    cleanup();
  }
}
```

### 4.4 Run (expect pass)

```bash
cd frontend && npm test -- --run src/lib/reader/paginator.test.ts
```

Expected: 2 passed.

### 4.5 Commit

```bash
git add frontend/src/lib/reader/paginator.ts frontend/src/lib/reader/paginator.test.ts
git commit -m "Slice R1 T4: DOM paginator that chunks anchored paragraphs into spreads"
```

---

## Task 5 — Reading cursor + localStorage hook

**Goal:** `useReadingCursor(bookId, chapter, firstSid)` persists to `bookrag.cursor.{bookId}` and never rewinds on backward navigation. AC 10–12.

**Create:** `frontend/src/lib/reader/useReadingCursor.ts`
**Create:** `frontend/src/lib/reader/useReadingCursor.test.tsx`

### 5.1 Failing test

`frontend/src/lib/reader/useReadingCursor.test.tsx`:

```tsx
/**
 * @vitest-environment jsdom
 */
import { describe, it, expect, beforeEach } from "vitest";
import { renderHook, act } from "@testing-library/react";
import { useReadingCursor, readStoredCursor, CURSOR_KEY } from "./useReadingCursor";

describe("useReadingCursor", () => {
  beforeEach(() => window.localStorage.clear());

  it("initializes to firstSid when no stored value", () => {
    const { result } = renderHook(() =>
      useReadingCursor("bk", 1, "p1.s1"),
    );
    expect(result.current.cursor).toBe("p1.s1");
  });

  it("advances forward only", () => {
    const { result } = renderHook(() =>
      useReadingCursor("bk", 1, "p1.s1"),
    );
    act(() => result.current.advanceTo("p2.s3"));
    expect(result.current.cursor).toBe("p2.s3");
    // Backward call must not rewind.
    act(() => result.current.advanceTo("p1.s5"));
    expect(result.current.cursor).toBe("p2.s3");
  });

  it("persists to localStorage under bookrag.cursor.{bookId}", () => {
    const { result } = renderHook(() =>
      useReadingCursor("bk", 1, "p1.s1"),
    );
    act(() => result.current.advanceTo("p3.s2"));
    const raw = window.localStorage.getItem(CURSOR_KEY("bk"));
    expect(raw).not.toBeNull();
    const parsed = JSON.parse(raw!);
    expect(parsed).toEqual({ chapter: 1, anchor: "p3.s2" });
  });

  it("restores from localStorage", () => {
    window.localStorage.setItem(
      CURSOR_KEY("bk"),
      JSON.stringify({ chapter: 1, anchor: "p4.s1" }),
    );
    expect(readStoredCursor("bk")).toEqual({ chapter: 1, anchor: "p4.s1" });
    const { result } = renderHook(() =>
      useReadingCursor("bk", 1, "p1.s1"),
    );
    expect(result.current.cursor).toBe("p4.s1");
  });
});
```

### 5.2 Run (expect failure)

```bash
cd frontend && npm test -- --run src/lib/reader/useReadingCursor.test.tsx
```

Expected: resolve failure — module missing.

### 5.3 Implement

`frontend/src/lib/reader/useReadingCursor.ts`:

```ts
import { useCallback, useEffect, useState } from "react";
import { compareSid } from "./sidCompare";

export const CURSOR_KEY = (bookId: string) => `bookrag.cursor.${bookId}`;

export type StoredCursor = { chapter: number; anchor: string };

export function readStoredCursor(bookId: string): StoredCursor | null {
  try {
    const raw = window.localStorage.getItem(CURSOR_KEY(bookId));
    if (!raw) return null;
    const v = JSON.parse(raw);
    if (typeof v?.chapter === "number" && typeof v?.anchor === "string") return v;
    return null;
  } catch {
    return null;
  }
}

export function useReadingCursor(
  bookId: string,
  chapter: number,
  firstSid: string,
) {
  const [cursor, setCursor] = useState<string>(() => {
    const stored = readStoredCursor(bookId);
    if (stored && stored.chapter === chapter) return stored.anchor;
    return firstSid;
  });

  // If bookId or chapter changes, re-seed from storage or firstSid.
  useEffect(() => {
    const stored = readStoredCursor(bookId);
    if (stored && stored.chapter === chapter) setCursor(stored.anchor);
    else setCursor(firstSid);
  }, [bookId, chapter, firstSid]);

  const advanceTo = useCallback(
    (sid: string) => {
      setCursor((prev) => {
        if (compareSid(sid, prev) <= 0) return prev;
        try {
          window.localStorage.setItem(
            CURSOR_KEY(bookId),
            JSON.stringify({ chapter, anchor: sid }),
          );
        } catch {
          /* ignore quota */
        }
        return sid;
      });
    },
    [bookId, chapter],
  );

  return { cursor, advanceTo };
}
```

### 5.4 Run (expect pass)

```bash
cd frontend && npm test -- --run src/lib/reader/useReadingCursor.test.tsx
```

Expected: 4 passed.

### 5.5 Commit

```bash
git add frontend/src/lib/reader/useReadingCursor.ts frontend/src/lib/reader/useReadingCursor.test.tsx
git commit -m "Slice R1 T5: useReadingCursor with forward-only advance + localStorage"
```

---

## Task 6 — `BookSpread` + `Page` layout components

**Goal:** Render two pages side by side with book shadow, spine gradient, chapter stave, chapter title, drop cap on first paragraph, folio. Accepts `Page[]` for left + right.

**Create:** `frontend/src/components/reader/BookSpread.tsx`
**Create:** `frontend/src/components/reader/BookSpread.test.tsx`

### 6.1 Failing test

`frontend/src/components/reader/BookSpread.test.tsx`:

```tsx
/**
 * @vitest-environment jsdom
 */
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { BookSpread } from "./BookSpread";
import type { Page } from "../../lib/reader/paginator";

const leftPage: Page = [
  {
    paragraph_idx: 1,
    sentences: [
      { sid: "p1.s1", text: "Alpha." },
      { sid: "p1.s2", text: "Bravo." },
    ],
  },
];
const rightPage: Page = [
  {
    paragraph_idx: 2,
    sentences: [{ sid: "p2.s1", text: "Charlie." }],
  },
];

describe("BookSpread", () => {
  it("renders both pages with sentence data-sid", () => {
    render(
      <BookSpread
        chapterNum={1}
        chapterTitle="Marley's Ghost"
        totalChapters={5}
        left={leftPage}
        right={rightPage}
        folioLeft={1}
        folioRight={2}
        cursor="p1.s1"
      />,
    );
    expect(document.querySelector('[data-sid="p1.s1"]')).not.toBeNull();
    expect(document.querySelector('[data-sid="p1.s2"]')).not.toBeNull();
    expect(document.querySelector('[data-sid="p2.s1"]')).not.toBeNull();
    expect(screen.getByText(/Marley's Ghost/)).toBeInTheDocument();
  });

  it("marks first paragraph of the chapter with drop cap on first spread", () => {
    render(
      <BookSpread
        chapterNum={1}
        chapterTitle="T"
        totalChapters={1}
        left={leftPage}
        right={[]}
        folioLeft={1}
        folioRight={2}
        cursor="p1.s1"
        isFirstSpread={true}
      />,
    );
    expect(document.querySelector(".rr-dropcap")).not.toBeNull();
  });
});
```

### 6.2 Run (expect failure)

```bash
cd frontend && npm test -- --run src/components/reader/BookSpread.test.tsx
```

### 6.3 Implement

`frontend/src/components/reader/BookSpread.tsx`:

```tsx
import { Paragraph } from "./Paragraph";
import type { Page } from "../../lib/reader/paginator";

function PageSide({
  page,
  cursor,
  dropCapFirst,
  folio,
  chapterHeader,
}: {
  page: Page;
  cursor: string;
  dropCapFirst: boolean;
  folio: number;
  chapterHeader?: { num: number; title: string; totalChapters: number };
}) {
  return (
    <div
      className="rr-page"
      style={{
        background: "var(--paper-00)",
        padding: "52px 44px 40px",
        position: "relative",
        minHeight: 720,
        fontFamily: "var(--serif)",
        fontSize: 15,
        lineHeight: 1.72,
        color: "var(--ink-0)",
      }}
    >
      {chapterHeader && (
        <>
          <div
            style={{
              fontFamily: "var(--serif)",
              fontStyle: "italic",
              fontSize: 11.5,
              letterSpacing: 0.4,
              color: "var(--ink-3)",
              marginBottom: 10,
            }}
          >
            Chapter {chapterHeader.num} · of {chapterHeader.totalChapters}
          </div>
          <h2
            style={{
              margin: "0 0 26px",
              fontFamily: "var(--serif)",
              fontWeight: 400,
              fontSize: 22,
              letterSpacing: -0.3,
              color: "var(--ink-0)",
            }}
          >
            {chapterHeader.title}
          </h2>
        </>
      )}
      {page.map((p, i) => (
        <Paragraph
          key={`${p.paragraph_idx}-${i}`}
          paragraphIdx={p.paragraph_idx}
          sentences={p.sentences}
          fogStartSid={cursor}
          dropCap={dropCapFirst && i === 0 && !p.isContinuation}
        />
      ))}
      <div
        style={{
          position: "absolute",
          bottom: 18,
          left: 44,
          right: 44,
          display: "flex",
          justifyContent: "space-between",
          fontFamily: "var(--serif)",
          fontStyle: "italic",
          fontSize: 11,
          color: "var(--ink-3)",
        }}
      >
        <span style={{ fontFamily: "var(--mono)" }}>{folio}</span>
      </div>
    </div>
  );
}

export function BookSpread({
  chapterNum,
  chapterTitle,
  totalChapters,
  left,
  right,
  folioLeft,
  folioRight,
  cursor,
  isFirstSpread = false,
}: {
  chapterNum: number;
  chapterTitle: string;
  totalChapters: number;
  left: Page;
  right: Page;
  folioLeft: number;
  folioRight: number;
  cursor: string;
  isFirstSpread?: boolean;
}) {
  return (
    <div
      className="rr-spread"
      data-testid="book-spread"
      style={{
        display: "grid",
        gridTemplateColumns: "1fr 1fr",
        background: "var(--paper-00)",
        borderRadius: 3,
        boxShadow:
          "0 30px 70px -24px rgba(28,24,18,.2), 0 10px 20px -8px rgba(28,24,18,.08)",
        position: "relative",
        overflow: "hidden",
      }}
    >
      <PageSide
        page={left}
        cursor={cursor}
        dropCapFirst={isFirstSpread}
        folio={folioLeft}
        chapterHeader={
          isFirstSpread
            ? { num: chapterNum, title: chapterTitle, totalChapters }
            : undefined
        }
      />
      <PageSide page={right} cursor={cursor} dropCapFirst={false} folio={folioRight} />
      <div
        aria-hidden="true"
        style={{
          position: "absolute",
          left: "calc(50% - 15px)",
          top: 0,
          bottom: 0,
          width: 30,
          background:
            "linear-gradient(to right, transparent 0%, color-mix(in oklab, var(--ink-0) 7%, transparent) 50%, transparent 100%)",
          pointerEvents: "none",
        }}
      />
    </div>
  );
}
```

### 6.4 Run (expect pass)

```bash
cd frontend && npm test -- --run src/components/reader/BookSpread.test.tsx
```

### 6.5 Commit

```bash
git add frontend/src/components/reader/BookSpread.tsx frontend/src/components/reader/BookSpread.test.tsx
git commit -m "Slice R1 T6: BookSpread and Page layout with spine + drop cap"
```

---

## Task 7 — Replace `ReadingScreen.tsx` and remove old tests

**Goal:** Replace `ReadingScreen` with the new spread surface. Wire paginator + cursor + keyboard. Delete/replace the existing `ReadingScreen.test.tsx` which exercised the annotation panel / selection toolbar (entirely out-of-scope for R1).

**Modify:** `frontend/src/screens/ReadingScreen.tsx`
**Delete:** `frontend/src/screens/ReadingScreen.test.tsx` (replaced by new minimal test)
**Create:** `frontend/src/screens/ReadingScreen.test.tsx` (new, minimal)

### 7.1 Failing test

Overwrite `frontend/src/screens/ReadingScreen.test.tsx` with:

```tsx
/**
 * @vitest-environment jsdom
 */
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, waitFor, act } from "@testing-library/react";
import { MemoryRouter, Routes, Route } from "react-router-dom";
import { ReadingScreen } from "./ReadingScreen";

function mockFetch(response: Record<string, unknown>) {
  return vi.fn(async () =>
    new Response(JSON.stringify(response), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    }),
  ) as typeof fetch;
}

const CH = {
  num: 1,
  title: "Marley's Ghost",
  paragraphs: ["Alpha. Bravo.", "Charlie."],
  paragraphs_anchored: [
    {
      paragraph_idx: 1,
      sentences: [
        { sid: "p1.s1", text: "Alpha." },
        { sid: "p1.s2", text: "Bravo." },
      ],
    },
    {
      paragraph_idx: 2,
      sentences: [{ sid: "p2.s1", text: "Charlie." }],
    },
  ],
  anchors_fallback: false,
  has_prev: false,
  has_next: true,
  total_chapters: 5,
};

describe("ReadingScreen — slice R1", () => {
  const realFetch = global.fetch;
  beforeEach(() => {
    window.localStorage.clear();
    global.fetch = mockFetch(CH);
  });
  afterEach(() => {
    global.fetch = realFetch;
  });

  function renderAt(path = "/books/carol/read/1") {
    return render(
      <MemoryRouter initialEntries={[path]}>
        <Routes>
          <Route
            path="/books/:bookId/read/:chapterNum"
            element={<ReadingScreen />}
          />
        </Routes>
      </MemoryRouter>,
    );
  }

  it("renders a two-page spread with data-sid sentences", async () => {
    renderAt();
    await waitFor(() =>
      expect(screen.getByTestId("book-spread")).toBeInTheDocument(),
    );
    expect(document.querySelector('[data-sid="p1.s1"]')).not.toBeNull();
    expect(document.querySelector('[data-sid="p2.s1"]')).not.toBeNull();
  });

  it("ArrowRight at last spread does nothing (no crash)", async () => {
    renderAt();
    await waitFor(() => screen.getByTestId("book-spread"));
    act(() => {
      window.dispatchEvent(new KeyboardEvent("keydown", { key: "ArrowRight" }));
      window.dispatchEvent(new KeyboardEvent("keydown", { key: "ArrowRight" }));
    });
    // Still on screen.
    expect(screen.getByTestId("book-spread")).toBeInTheDocument();
  });

  it("initial cursor is p1.s1 when storage empty", async () => {
    renderAt();
    await waitFor(() => screen.getByTestId("book-spread"));
    // The first sentence should be un-fogged (opacity:1); later sentences fogged.
    const first = document.querySelector('[data-sid="p1.s1"]') as HTMLElement;
    expect(first.getAttribute("style") ?? "").toMatch(/opacity:\s*1/);
  });
});
```

### 7.2 Run (expect failure)

```bash
cd frontend && npm test -- --run src/screens/ReadingScreen.test.tsx
```

Expected: old ReadingScreen renders panel/rail/selection-toolbar markup — tests referencing `book-spread` testid fail.

### 7.3 Implement — replace `ReadingScreen.tsx`

`frontend/src/screens/ReadingScreen.tsx`:

```tsx
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { fetchChapter, type Chapter } from "../lib/api";
import { paginate, type Spread } from "../lib/reader/paginator";
import { BookSpread } from "../components/reader/BookSpread";
import { useReadingCursor } from "../lib/reader/useReadingCursor";

type Body =
  | { kind: "loading" }
  | { kind: "error"; message: string }
  | { kind: "ok"; chapter: Chapter; spreads: Spread[] };

export function ReadingScreen() {
  const { bookId = "", chapterNum = "1" } = useParams<{
    bookId: string;
    chapterNum: string;
  }>();
  const n = Number.parseInt(chapterNum, 10) || 1;
  const navigate = useNavigate();

  const [body, setBody] = useState<Body>({ kind: "loading" });
  const [spreadIdx, setSpreadIdx] = useState(0);
  const stageRef = useRef<HTMLDivElement | null>(null);

  // Load chapter and paginate.
  useEffect(() => {
    let cancelled = false;
    setBody({ kind: "loading" });
    fetchChapter(bookId, n)
      .then((chapter) => {
        if (cancelled) return;
        const box = {
          pageWidth: 440,
          pageHeight: 720,
          paddingPx: 48,
          fontPx: 15,
          lineHeight: 1.72,
        };
        const spreads = paginate(chapter.paragraphs_anchored, box);
        setSpreadIdx(0);
        setBody({ kind: "ok", chapter, spreads });
      })
      .catch((err: unknown) => {
        if (cancelled) return;
        setBody({
          kind: "error",
          message: err instanceof Error ? err.message : String(err),
        });
      });
    return () => {
      cancelled = true;
    };
  }, [bookId, n]);

  const firstSid =
    body.kind === "ok" ? body.spreads[0]?.firstSid ?? "p1.s1" : "p1.s1";
  const { cursor, advanceTo } = useReadingCursor(bookId, n, firstSid);

  const current: Spread | null =
    body.kind === "ok" ? body.spreads[spreadIdx] ?? null : null;

  const turnForward = useCallback(() => {
    if (body.kind !== "ok") return;
    if (spreadIdx >= body.spreads.length - 1) return;
    const next = spreadIdx + 1;
    setSpreadIdx(next);
    const nextSpread = body.spreads[next];
    if (nextSpread) advanceTo(nextSpread.lastSid);
  }, [body, spreadIdx, advanceTo]);

  const turnBackward = useCallback(() => {
    if (body.kind !== "ok") return;
    if (spreadIdx <= 0) return;
    setSpreadIdx(spreadIdx - 1);
    // Cursor does NOT rewind (AC 10).
  }, [body, spreadIdx]);

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.key === "ArrowRight") {
        e.preventDefault();
        turnForward();
      } else if (e.key === "ArrowLeft") {
        e.preventDefault();
        turnBackward();
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [turnForward, turnBackward]);

  const title = body.kind === "ok" ? body.chapter.title : "";
  const total = body.kind === "ok" ? body.chapter.total_chapters : 0;

  return (
    <div
      className="br"
      style={{ minHeight: "100vh", background: "var(--paper-0)" }}
      data-testid="reading-screen"
    >
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "1fr auto 1fr",
          alignItems: "center",
          padding: "14px 28px",
          height: 52,
          borderBottom: "var(--hairline)",
        }}
      >
        <button
          type="button"
          onClick={() => navigate("/")}
          style={{
            fontFamily: "var(--sans)",
            fontSize: 13,
            color: "var(--ink-1)",
            justifySelf: "start",
            background: "transparent",
            border: 0,
            cursor: "pointer",
          }}
          aria-label="Back to library"
        >
          ← Library
        </button>
        <div
          style={{
            fontFamily: "var(--serif)",
            fontStyle: "italic",
            fontSize: 14,
            color: "var(--ink-0)",
          }}
        >
          {title}
        </div>
        <div
          aria-hidden="true"
          style={{ justifySelf: "end", color: "var(--ink-3)", fontSize: 12 }}
        >
          {body.kind === "ok"
            ? `${spreadIdx + 1} / ${body.spreads.length}`
            : ""}
        </div>
      </div>

      <div
        ref={stageRef}
        style={{
          padding: "24px",
          display: "grid",
          placeItems: "center",
          minHeight: "calc(100vh - 52px)",
        }}
      >
        {body.kind === "loading" && (
          <div role="status" style={{ color: "var(--ink-2)" }}>
            Loading chapter…
          </div>
        )}
        {body.kind === "error" && (
          <div role="alert" style={{ color: "var(--err)" }}>
            Couldn't load the chapter. ({body.message})
          </div>
        )}
        {body.kind === "ok" && current && (
          <div style={{ width: "min(1100px, 100%)" }}>
            <BookSpread
              chapterNum={body.chapter.num}
              chapterTitle={body.chapter.title}
              totalChapters={total}
              left={current.left}
              right={current.right}
              folioLeft={spreadIdx * 2 + 1}
              folioRight={spreadIdx * 2 + 2}
              cursor={cursor}
              isFirstSpread={spreadIdx === 0}
            />
          </div>
        )}
      </div>
    </div>
  );
}
```

### 7.4 Run (expect pass)

```bash
cd frontend && npm test -- --run src/screens/ReadingScreen.test.tsx
```

Then run the full Vitest suite to ensure no other test imports the removed symbols (`useReadingState`, the annotation flow, etc. are still present in the codebase but orphaned from `ReadingScreen`; they're still imported by their own tests — leave them):

```bash
cd frontend && npm test -- --run
```

Expected: new ReadingScreen tests pass. Previously failing or now-stale behavior tests (pre-R1 panel flow) that were in the old `ReadingScreen.test.tsx` are gone. If any other test file imports symbols exported only by the old `ReadingScreen`, resolve by leaving the helper files (`screens/reading/useReadingState.ts` etc.) in place — they are not deleted. Do not delete them in R1 (out-of-scope deferred helpers).

### 7.5 Commit

```bash
git add frontend/src/screens/ReadingScreen.tsx frontend/src/screens/ReadingScreen.test.tsx
git commit -m "Slice R1 T7: replace ReadingScreen with two-page spread + cursor + keyboard"
```

---

## Task 8 — Playwright evaluator gate

**Goal:** `frontend/e2e/slice-R1-reading-surface.spec.ts` covers every PRD acceptance criterion that's exercisable through the UI.

**Create:** `frontend/e2e/slice-R1-reading-surface.spec.ts`

### 8.1 Create spec

```ts
import { test, expect } from "@playwright/test";
import type { Page, Route } from "@playwright/test";

const BOOK_ID = "carol";

type ChapterResponse = {
  num: number;
  title: string;
  total_chapters: number;
  has_prev: boolean;
  has_next: boolean;
  paragraphs: string[];
  paragraphs_anchored: {
    paragraph_idx: number;
    sentences: { sid: string; text: string }[];
  }[];
  anchors_fallback: boolean;
};

function makeChapter(n: number, numParagraphs = 8): ChapterResponse {
  const paragraphs_anchored = Array.from({ length: numParagraphs }, (_, pi) => {
    const p = pi + 1;
    const sCount = 4 + (pi % 3);
    const sentences = Array.from({ length: sCount }, (_, si) => ({
      sid: `p${p}.s${si + 1}`,
      text:
        `This is sentence ${si + 1} of paragraph ${p} in chapter ${n}. ` +
        `It is deliberately padded with enough words to produce multiple lines ` +
        `of rendered justified prose so pagination actually splits.`,
    }));
    return { paragraph_idx: p, sentences };
  });
  const paragraphs = paragraphs_anchored.map((p) =>
    p.sentences.map((s) => s.text).join(" "),
  );
  return {
    num: n,
    title: `Chapter ${n}`,
    total_chapters: 3,
    has_prev: n > 1,
    has_next: n < 3,
    paragraphs,
    paragraphs_anchored,
    anchors_fallback: false,
  };
}

async function mockBooks(page: Page) {
  await page.route("http://localhost:8000/books", async (route: Route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify([
        {
          book_id: BOOK_ID,
          title: "Carol",
          total_chapters: 3,
          current_chapter: 1,
          ready_for_query: true,
        },
      ]),
    });
  });
}

async function mockChapter(page: Page) {
  await page.route(
    new RegExp(`^http://localhost:8000/books/${BOOK_ID}/chapters/(\\d+)$`),
    async (route: Route) => {
      const url = route.request().url();
      const n = Number.parseInt(url.split("/").pop() ?? "1", 10);
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(makeChapter(n)),
      });
    },
  );
}

test.describe("Slice R1 — reading surface", () => {
  test.beforeEach(async ({ page }) => {
    await mockBooks(page);
    await mockChapter(page);
  });

  test("renders a two-page spread", async ({ page }) => {
    await page.goto(`/books/${BOOK_ID}/read/1`);
    await expect(page.getByTestId("book-spread")).toBeVisible();
  });

  test("sentences carry data-sid p{n}.s{m}", async ({ page }) => {
    await page.goto(`/books/${BOOK_ID}/read/1`);
    await expect(page.locator('[data-sid="p1.s1"]')).toBeVisible();
    const sids = await page.$$eval("[data-sid]", (els) =>
      els.map((e) => e.getAttribute("data-sid") ?? ""),
    );
    for (const sid of sids) {
      expect(sid).toMatch(/^p\d+\.s\d+$/);
    }
  });

  test("ArrowRight advances spread + cursor; ArrowLeft goes back without rewinding cursor", async ({
    page,
  }) => {
    await page.goto(`/books/${BOOK_ID}/read/1`);
    await expect(page.getByTestId("book-spread")).toBeVisible();

    const cursorAfter = async () =>
      await page.evaluate(() => {
        const raw = localStorage.getItem(`bookrag.cursor.${"carol"}`);
        return raw ? JSON.parse(raw).anchor : null;
      });

    await page.keyboard.press("ArrowRight");
    const c1 = await cursorAfter();
    expect(c1).not.toBeNull();

    await page.keyboard.press("ArrowLeft");
    const c2 = await cursorAfter();
    // Cursor did NOT rewind.
    expect(c2).toBe(c1);
  });

  test("post-cursor sentences are fogged (opacity < 0.5)", async ({ page }) => {
    await page.goto(`/books/${BOOK_ID}/read/1`);
    await expect(page.locator('[data-sid="p1.s1"]')).toBeVisible();
    // On initial mount, cursor = first sentence; everything after p1.s1 is fogged.
    const laterOpacity = await page
      .locator('[data-sid="p1.s2"]')
      .first()
      .evaluate((el) => parseFloat(getComputedStyle(el).opacity || "1"));
    expect(laterOpacity).toBeLessThan(0.5);
    const firstOpacity = await page
      .locator('[data-sid="p1.s1"]')
      .first()
      .evaluate((el) => parseFloat(getComputedStyle(el).opacity || "1"));
    expect(firstOpacity).toBeGreaterThan(0.9);
  });

  test("reload restores cursor from localStorage", async ({ page }) => {
    await page.goto(`/books/${BOOK_ID}/read/1`);
    await expect(page.getByTestId("book-spread")).toBeVisible();
    await page.keyboard.press("ArrowRight");
    const before = await page.evaluate(() =>
      localStorage.getItem(`bookrag.cursor.carol`),
    );
    expect(before).not.toBeNull();
    await page.reload();
    await expect(page.getByTestId("book-spread")).toBeVisible();
    const after = await page.evaluate(() =>
      localStorage.getItem(`bookrag.cursor.carol`),
    );
    expect(after).toBe(before);
  });

  test("ArrowRight past the last spread does not crash", async ({ page }) => {
    await page.goto(`/books/${BOOK_ID}/read/1`);
    await expect(page.getByTestId("book-spread")).toBeVisible();
    for (let i = 0; i < 30; i++) await page.keyboard.press("ArrowRight");
    await expect(page.getByTestId("book-spread")).toBeVisible();
  });

  test("ArrowLeft before the first spread does not crash", async ({ page }) => {
    await page.goto(`/books/${BOOK_ID}/read/1`);
    await expect(page.getByTestId("book-spread")).toBeVisible();
    for (let i = 0; i < 5; i++) await page.keyboard.press("ArrowLeft");
    await expect(page.getByTestId("book-spread")).toBeVisible();
  });
});
```

### 8.2 Run (expect pass)

```bash
cd frontend && npx playwright test e2e/slice-R1-reading-surface.spec.ts
```

Expected: 7 passed.

### 8.3 Commit

```bash
git add frontend/e2e/slice-R1-reading-surface.spec.ts
git commit -m "Slice R1 T8: Playwright evaluator gate covering PRD acceptance criteria"
```

---

## Task 9 — Final sweep + regression run

**Goal:** Confirm no regressions; confirm unit and backend tests still green end-to-end.

### 9.1 Run everything

```bash
source .venv/bin/activate && pytest tests/ -v --tb=short
```

Expected: all backend tests pass (923 existing + 3 new = 926).

```bash
cd frontend && npm test -- --run
```

Expected: all Vitest suites pass, new tests included.

```bash
cd frontend && npx playwright test
```

Expected: all E2E specs pass including the new R1 spec.

### 9.2 Commit (only if any follow-up touch was needed)

If any small fix was required:

```bash
git add -u
git commit -m "Slice R1 T9: regression fixes after full suite sweep"
```

Otherwise skip. Slice R1 is complete.

---

## Summary

**9 tasks.** Backend files touched: `api/loaders/sentence_anchors.py` (new), `api/loaders/book_data.py` (extended `Chapter` + `load_chapter`), `tests/test_sentence_anchors.py` (new). Frontend created: `frontend/src/components/reader/{Sentence,Paragraph,BookSpread}.tsx` + tests, `frontend/src/lib/reader/{paginator,sidCompare,useReadingCursor}.ts` + tests, `frontend/src/lib/api.anchors.test.ts`, `frontend/e2e/slice-R1-reading-surface.spec.ts`. Frontend modified: `frontend/src/lib/api.ts` (anchor types), `frontend/src/styles/tokens.css` (synced to handoff), `frontend/src/screens/ReadingScreen.tsx` (replaced in place), `frontend/src/screens/ReadingScreen.test.tsx` (replaced with new minimal R1 tests). Frontend deleted: none (orphan helper files `screens/reading/useReadingState.ts`, `useChatState.ts`, plus existing panel/annotation components, are deliberately left alone in R1 — they are covered by their own tests and will be revisited in R2+). Playwright spec name: `frontend/e2e/slice-R1-reading-surface.spec.ts`.

---

