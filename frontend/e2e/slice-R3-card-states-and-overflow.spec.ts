import { test, expect, type Page, type Route } from "@playwright/test";

const BOOK_ID = "carol";

type ChapterSize = "small" | "large";

function makeChapter(n: number, size: ChapterSize = "small") {
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

  // Group by paragraph_idx derived from sid "p{n}.s{m}".
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

type MockOpts = {
  chapterSize?: ChapterSize;
  queryDelayMs?: number;
  answer?: string;
};

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

test.describe("Slice R3 — card states S1–S7 + O2 overflow", () => {
  test("AC1 S1 invitation shown with zero cards", async ({ page }) => {
    await mockAll(page);
    await page.addInitScript(() => {
      try {
        window.localStorage.clear();
      } catch {
        /* ignore */
      }
    });
    await page.goto(`/books/${BOOK_ID}/read/1`);
    await expect(page.getByTestId("book-spread")).toBeVisible();
    await expect(page.getByTestId("s1-empty-card")).toBeVisible();
  });

  test("AC2 S2 connector SVG present with one card, absent with two", async ({
    page,
  }) => {
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

    // Seed a second card — connector should disappear.
    await selectInSid(page, "p1.s2");
    await page.getByRole("button", { name: "Note" }).click();
    await page.getByTestId("note-body").first().fill("a");
    await page.getByTestId("note-body").first().press("Enter");
    await expect(page.getByTestId("anchor-connector")).toHaveCount(0);
  });

  test("AC3 S3 skeleton then blinking cursor during ask", async ({ page }) => {
    await mockAll(page, { queryDelayMs: 400 });
    await page.goto(`/books/${BOOK_ID}/read/1`);
    await expect(page.getByTestId("book-spread")).toBeVisible();
    await selectInSid(page, "p1.s1");
    await page.locator('[data-testid="selection-toolbar"] [aria-label="Ask"]').click();
    await expect(page.getByTestId("skeleton-ask-card")).toBeVisible();
    await expect(page.getByTestId("blinking-cursor")).toBeVisible({
      timeout: 2000,
    });
    await expect(page.getByTestId("ask-answer").first()).toContainText(
      "synthesized answer",
      { timeout: 8000 },
    );
    await expect(page.getByTestId("blinking-cursor")).toHaveCount(0);
  });

  test("AC4 S4 scrollable + fade on long answer", async ({ page }) => {
    const longAnswer = "lorem ipsum ".repeat(400);
    await mockAll(page, { answer: longAnswer });
    await page.goto(`/books/${BOOK_ID}/read/1`);
    await expect(page.getByTestId("book-spread")).toBeVisible();
    await selectInSid(page, "p1.s1");
    await page.locator('[data-testid="selection-toolbar"] [aria-label="Ask"]').click();
    const answer = page.getByTestId("ask-answer").first();
    await expect(answer).toContainText("lorem ipsum", { timeout: 8000 });
    const overflowY = await answer.evaluate(
      (el) => getComputedStyle(el).overflowY,
    );
    expect(overflowY).toBe("auto");
    await expect(page.getByTestId("ask-answer-fade")).toBeVisible();
  });

  test("AC5 S5 follow-up composer appends threaded reply", async ({ page }) => {
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
    const followup = page.locator('[data-testid="followup"]').first();
    await expect(followup).toBeVisible({ timeout: 5000 });
    await expect(followup).toContainText("synthesized answer", {
      timeout: 5000,
    });
  });

  test("AC5b duplicate-ask focuses the existing card's follow-up composer", async ({
    page,
  }) => {
    await mockAll(page);
    await page.goto(`/books/${BOOK_ID}/read/1`);
    await expect(page.getByTestId("book-spread")).toBeVisible();
    await selectInSid(page, "p1.s1");
    await page.locator('[data-testid="selection-toolbar"] [aria-label="Ask"]').click();
    await expect(page.getByTestId("ask-answer").first()).toContainText(
      "synthesized answer",
      { timeout: 5000 },
    );
    // Re-select the same sid and press Ask again.
    await selectInSid(page, "p1.s1");
    await page.locator('[data-testid="selection-toolbar"] [aria-label="Ask"]').click();
    const focusedPlaceholder = await page.evaluate(
      () => (document.activeElement as HTMLInputElement | null)?.placeholder,
    );
    expect(focusedPlaceholder ?? "").toMatch(/Ask a follow-up/i);
  });

  test("AC6 S6 off-screen prefix + edge bar + jump CTA", async ({ page }) => {
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
    // Scroll the anchor out of view.
    await page.evaluate(() => window.scrollTo(0, 4000));
    await expect(page.locator("text=↑ SCROLL UP ·")).toBeVisible({
      timeout: 3000,
    });
    await expect(page.getByTestId("anchor-edge-bar")).toBeVisible();
    await expect(page.getByTestId("jump-to-anchor-cta")).toBeVisible();
    await page.getByTestId("jump-to-anchor-cta").click();
    // After jumping, anchor is back in view (scrollY much smaller).
    const y = await page.evaluate(() => window.scrollY);
    expect(y).toBeLessThan(4000);
  });

  test("AC7 S7 cross-page prefix on a card anchored to the left page of the current spread", async ({
    page,
  }) => {
    await mockAll(page, { chapterSize: "large" });
    await page.goto(`/books/${BOOK_ID}/read/1`);
    await expect(page.getByTestId("book-spread")).toBeVisible();
    // Ask about p1.s1 — which is on the LEFT page of spread 0.
    // The margin column sits on the right side, so this card gets the
    // intra-spread "← FROM p. 1 ·" prefix immediately (no page turn needed).
    await selectInSid(page, "p1.s1");
    await page.locator('[data-testid="selection-toolbar"] [aria-label="Ask"]').click();
    await expect(page.getByTestId("ask-answer").first()).toContainText(
      "synthesized answer",
      { timeout: 5000 },
    );
    // The cross-page prefix should appear because p1.s1 is on the left page.
    const prefix = page.locator("text=← FROM p. 1 ·");
    await expect(prefix).toBeVisible({ timeout: 3000 });
    // After turning to spread 1, the card should NOT be visible (cross-spread cards hidden).
    await page.keyboard.press("ArrowRight");
    await page.waitForTimeout(200);
    await expect(page.getByTestId("s1-empty-card")).toBeVisible({ timeout: 2000 });
  });

  test("AC8/9/10 O2 collapse with 3+ cards, divider, and expand-on-click", async ({
    page,
  }) => {
    await mockAll(page);
    // Pre-seed 3 ask cards in localStorage before navigation.
    await page.addInitScript((bookId) => {
      const now = Date.now();
      const cards = [
        {
          id: "c1",
          bookId,
          anchor: "p1.s1",
          quote: "q1",
          chapter: 1,
          kind: "ask",
          question: "First question?",
          answer: "First answer.",
          followups: [],
          createdAt: new Date(now - 3000).toISOString(),
          updatedAt: new Date(now - 3000).toISOString(),
        },
        {
          id: "c2",
          bookId,
          anchor: "p1.s2",
          quote: "q2",
          chapter: 1,
          kind: "ask",
          question: "Second question?",
          answer: "Second answer.",
          followups: [],
          createdAt: new Date(now - 2000).toISOString(),
          updatedAt: new Date(now - 2000).toISOString(),
        },
        {
          id: "c3",
          bookId,
          anchor: "p1.s3",
          quote: "q3",
          chapter: 1,
          kind: "ask",
          question: "Third question?",
          answer: "Third answer.",
          followups: [],
          createdAt: new Date(now - 1000).toISOString(),
          updatedAt: new Date(now - 1000).toISOString(),
        },
      ];
      window.localStorage.setItem(
        `bookrag.cards.${bookId}`,
        JSON.stringify({ version: 1, cards }),
      );
    }, BOOK_ID);

    await page.goto(`/books/${BOOK_ID}/read/1`);
    await expect(page.getByTestId("book-spread")).toBeVisible();
    await expect(page.getByTestId("collapsed-card-row")).toHaveCount(1);
    await expect(page.getByTestId("latest-expanded-divider")).toBeVisible();
    await expect(page.locator("[data-card-kind='ask']")).toHaveCount(2);

    // Click the collapsed row — previously oldest-expanded should collapse.
    await page.getByTestId("collapsed-card-row").first().click();
    await expect(page.getByTestId("collapsed-card-row")).toHaveCount(1);
    await expect(page.locator("[data-card-kind='ask']")).toHaveCount(2);
    // The promoted card (c1 was collapsed, click expands it) should be present.
    await expect(page.locator("[data-card-id='c1']")).toBeVisible();
  });
});
