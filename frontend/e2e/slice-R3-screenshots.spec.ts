import { test, expect, type Page, type Route } from "@playwright/test";
import path from "node:path";

const BOOK_ID = "carol";
const ASSETS_DIR = path.resolve(
  process.cwd(),
  "../docs/superpowers/reviews/assets/2026-04-22-slice-R3",
);

function shot(page: Page, name: string) {
  return page.screenshot({ path: path.join(ASSETS_DIR, name), fullPage: true });
}

type Size = "small" | "large";

function makeChapter(n: number, size: Size = "small") {
  const sentences =
    size === "large"
      ? Array.from({ length: 60 }).map((_, i) => ({
          sid: `p${Math.floor(i / 4) + 1}.s${(i % 4) + 1}`,
          text: `Sentence ${i + 1} padded out with enough words to force multiple spreads during pagination.`,
        }))
      : [
          { sid: "p1.s1", text: "Alpha sentence padded with more words for selection." },
          { sid: "p1.s2", text: "Bravo sentence padded with more words for selection." },
          { sid: "p1.s3", text: "Gamma sentence padded with more words for selection." },
        ];
  const byPara = new Map<number, { sid: string; text: string }[]>();
  for (const s of sentences) {
    const m = /^p(\d+)\.s\d+$/.exec(s.sid);
    const p = m ? parseInt(m[1], 10) : 1;
    const arr = byPara.get(p) ?? [];
    arr.push(s);
    byPara.set(p, arr);
  }
  const paragraphs_anchored = Array.from(byPara.entries()).map(
    ([paragraph_idx, sents]) => ({ paragraph_idx, sentences: sents }),
  );
  const paragraphs = paragraphs_anchored.map((p) =>
    p.sentences.map((s) => s.text).join(" "),
  );
  return {
    num: n,
    title: `Chapter ${n}`,
    total_chapters: 1,
    has_prev: false,
    has_next: false,
    paragraphs,
    paragraphs_anchored,
    anchors_fallback: false,
  };
}

type MockOpts = { chapterSize?: Size; queryDelayMs?: number; answer?: string };

async function mockAll(page: Page, opts: MockOpts = {}) {
  const size = opts.chapterSize ?? "small";
  const delay = opts.queryDelayMs ?? 0;
  const answer =
    opts.answer ??
    "This is a synthesized answer with enough words to observe streaming chunks landing over time.";
  await page.route("http://localhost:8000/books", async (route: Route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify([
        {
          book_id: BOOK_ID,
          title: "Carol",
          total_chapters: 1,
          current_chapter: 1,
          ready_for_query: true,
        },
      ]),
    });
  });
  await page.route(
    new RegExp(`^http://localhost:8000/books/${BOOK_ID}/chapters/(\\d+)$`),
    async (route: Route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(makeChapter(1, size)),
      });
    },
  );
  await page.route(
    `http://localhost:8000/books/${BOOK_ID}/query`,
    async (route: Route) => {
      if (delay > 0) await new Promise((r) => setTimeout(r, delay));
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          book_id: BOOK_ID,
          question: "q",
          search_type: "GRAPH_COMPLETION",
          current_chapter: 1,
          answer,
          results: [],
          result_count: 0,
        }),
      });
    },
  );
}

async function selectInSid(page: Page, sid: string) {
  await page.evaluate((s) => {
    const el = document.querySelector(`[data-sid="${s}"]`) as HTMLElement;
    const text = el.firstChild!;
    const range = document.createRange();
    range.setStart(text, 0);
    range.setEnd(text, 5);
    const sel = window.getSelection()!;
    sel.removeAllRanges();
    sel.addRange(range);
    document.dispatchEvent(new Event("selectionchange"));
  }, sid);
}

test.describe("Slice R3 screenshots", () => {
  test("ac1-s1-empty", async ({ page }) => {
    await mockAll(page);
    await page.addInitScript(() => {
      try { window.localStorage.clear(); } catch { /* ignore */ }
    });
    await page.goto(`/books/${BOOK_ID}/read/1`);
    await expect(page.getByTestId("s1-empty-card")).toBeVisible();
    await shot(page, "ac1-s1-empty.png");
  });

  test("ac2-s2-connector", async ({ page }) => {
    await mockAll(page);
    await page.goto(`/books/${BOOK_ID}/read/1`);
    await expect(page.getByTestId("book-spread")).toBeVisible();
    await selectInSid(page, "p1.s1");
    await page.locator('[data-testid="selection-toolbar"] [aria-label="Ask"]').click();
    await expect(page.getByTestId("ask-answer").first()).toContainText(
      "synthesized answer",
      { timeout: 5000 },
    );
    await expect(page.getByTestId("anchor-connector")).toBeVisible();
    await shot(page, "ac2-s2-connector.png");
  });

  test("ac3-s3-skeleton and cursor", async ({ page }) => {
    // Use a long streaming window so the cursor is visible for the shot.
    const longish = Array.from({ length: 200 })
      .map((_, i) => `word${i}`)
      .join(" ");
    await mockAll(page, { queryDelayMs: 400, answer: longish });
    await page.goto(`/books/${BOOK_ID}/read/1`);
    await expect(page.getByTestId("book-spread")).toBeVisible();
    await selectInSid(page, "p1.s1");
    await page.locator('[data-testid="selection-toolbar"] [aria-label="Ask"]').click();
    await expect(page.getByTestId("skeleton-ask-card")).toBeVisible();
    await shot(page, "ac3-s3-skeleton.png");
    await expect(page.getByTestId("blinking-cursor")).toBeVisible({
      timeout: 5000,
    });
    await shot(page, "ac3b-s3-cursor.png");
  });

  test("ac4-s4-long-answer", async ({ page }) => {
    const longAnswer = "lorem ipsum ".repeat(400);
    await mockAll(page, { answer: longAnswer });
    await page.goto(`/books/${BOOK_ID}/read/1`);
    await expect(page.getByTestId("book-spread")).toBeVisible();
    await selectInSid(page, "p1.s1");
    await page.locator('[data-testid="selection-toolbar"] [aria-label="Ask"]').click();
    await expect(page.getByTestId("ask-answer-fade")).toBeVisible({
      timeout: 10000,
    });
    await shot(page, "ac4-s4-long-answer.png");
  });

  test("ac5-s5-followup", async ({ page }) => {
    await mockAll(page);
    await page.goto(`/books/${BOOK_ID}/read/1`);
    await expect(page.getByTestId("book-spread")).toBeVisible();
    await selectInSid(page, "p1.s1");
    await page.locator('[data-testid="selection-toolbar"] [aria-label="Ask"]').click();
    await expect(page.getByTestId("ask-answer").first()).toContainText(
      "synthesized answer",
      { timeout: 5000 },
    );
    const composer = page.getByPlaceholder(/Ask a follow-up/i).first();
    await composer.fill("why?");
    await composer.press("Enter");
    await expect(page.locator('[data-testid="followup"]').first()).toContainText(
      "synthesized answer",
      { timeout: 5000 },
    );
    await shot(page, "ac5-s5-followup.png");
  });

  test("ac6-s6-offscreen", async ({ page }) => {
    await page.setViewportSize({ width: 1280, height: 400 });
    await mockAll(page);
    await page.goto(`/books/${BOOK_ID}/read/1`);
    await expect(page.getByTestId("book-spread")).toBeVisible();
    await selectInSid(page, "p1.s1");
    await page.locator('[data-testid="selection-toolbar"] [aria-label="Ask"]').click();
    await expect(page.getByTestId("ask-answer").first()).toContainText(
      "synthesized answer",
      { timeout: 5000 },
    );
    await page.evaluate(() => window.scrollTo(0, 4000));
    await expect(page.locator("text=↑ SCROLL UP ·")).toBeVisible({
      timeout: 3000,
    });
    await shot(page, "ac6-s6-offscreen.png");
  });

  test("ac7-s7-crosspage", async ({ page }) => {
    // S7 cross-page prefix fires for a card anchored on the LEFT page of the
    // current spread (intra-spread only — cross-spread cards are no longer shown).
    await mockAll(page, { chapterSize: "large" });
    await page.goto(`/books/${BOOK_ID}/read/1`);
    await expect(page.getByTestId("book-spread")).toBeVisible();
    await selectInSid(page, "p1.s1");
    await page.locator('[data-testid="selection-toolbar"] [aria-label="Ask"]').click();
    await expect(page.getByTestId("ask-answer").first()).toContainText(
      "synthesized answer",
      { timeout: 5000 },
    );
    // p1.s1 is on the left page of spread 0; the prefix fires immediately.
    await expect(page.locator("text=← FROM p. 1 ·")).toBeVisible({
      timeout: 3000,
    });
    await shot(page, "ac7-s7-crosspage.png");
  });

  test("ac8-o2-collapsed", async ({ page }) => {
    await mockAll(page);
    await page.addInitScript((bookId) => {
      const now = Date.now();
      const mk = (i: number, ago: number) => ({
        id: `c${i}`,
        bookId,
        anchor: `p1.s${i}`,
        quote: `q${i}`,
        chapter: 1,
        kind: "ask",
        question: `Question ${i}?`,
        answer: `Answer ${i}.`,
        followups: [],
        createdAt: new Date(now - ago).toISOString(),
        updatedAt: new Date(now - ago).toISOString(),
      });
      window.localStorage.setItem(
        `bookrag.cards.${bookId}`,
        JSON.stringify({
          version: 1,
          cards: [mk(1, 3000), mk(2, 2000), mk(3, 1000)],
        }),
      );
    }, BOOK_ID);
    await page.goto(`/books/${BOOK_ID}/read/1`);
    await expect(page.getByTestId("latest-expanded-divider")).toBeVisible();
    await expect(page.getByTestId("collapsed-card-row")).toHaveCount(1);
    await shot(page, "ac8-o2-collapsed.png");
  });
});
