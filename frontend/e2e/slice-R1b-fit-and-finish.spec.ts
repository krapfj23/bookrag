import { test, expect, type Page, type Route } from "@playwright/test";

const BOOK_ID = "carol";

/** Build a minimal chapter response with exactly the given sentences. */
function makeChapter(
  n: number,
  totalChapters: number,
  sids: { sid: string; text: string }[],
) {
  const byPara = new Map<number, { sid: string; text: string }[]>();
  for (const s of sids) {
    const m = /^p(\d+)\.s\d+$/.exec(s.sid);
    const p = m ? parseInt(m[1], 10) : 1;
    const arr = byPara.get(p) ?? [];
    arr.push(s);
    byPara.set(p, arr);
  }
  const paragraphs_anchored = Array.from(byPara.entries()).map(
    ([paragraph_idx, sentences]) => ({ paragraph_idx, sentences }),
  );
  const paragraphs = paragraphs_anchored.map((p) =>
    p.sentences.map((s) => s.text).join(" "),
  );
  return {
    num: n,
    title: `Chapter ${n}`,
    total_chapters: totalChapters,
    has_prev: n > 1,
    has_next: n < totalChapters,
    paragraphs,
    paragraphs_anchored,
    anchors_fallback: false,
  };
}

/** Short sids that fit on a single spread in any real browser. */
const SHORT_SIDS = [
  { sid: "p1.s1", text: "Alpha sentence." },
  { sid: "p1.s2", text: "Bravo sentence." },
];

/** Long sids designed to span two spreads (60 sentences). */
const LONG_SIDS = Array.from({ length: 60 }).map((_, i) => ({
  sid: `p${Math.floor(i / 4) + 1}.s${(i % 4) + 1}`,
  text: `Sentence ${i + 1} padded out with enough words to force multiple spreads during pagination.`,
}));

async function mockBooks(page: Page, totalChapters = 1) {
  await page.route("http://localhost:8000/books", async (route: Route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify([
        {
          book_id: BOOK_ID,
          title: "Carol",
          total_chapters: totalChapters,
          current_chapter: 1,
          ready_for_query: true,
        },
      ]),
    });
  });
}

async function mockChapter(
  page: Page,
  n: number,
  totalChapters: number,
  sids: { sid: string; text: string }[],
) {
  await page.route(
    new RegExp(`^http://localhost:8000/books/${BOOK_ID}/chapters/${n}$`),
    async (route: Route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(makeChapter(n, totalChapters, sids)),
      });
    },
  );
}

async function mockQuery(page: Page) {
  await page.route(
    `http://localhost:8000/books/${BOOK_ID}/query`,
    async (route: Route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          book_id: BOOK_ID,
          question: "q",
          search_type: "GRAPH_COMPLETION",
          current_chapter: 1,
          answer: "Synthesized answer for test.",
          results: [],
          result_count: 0,
        }),
      });
    },
  );
}

async function seedCards(
  page: Page,
  cards: object[],
) {
  await page.addInitScript((data: { bookId: string; cards: object[] }) => {
    try {
      window.localStorage.setItem(
        `bookrag.cards.${data.bookId}`,
        JSON.stringify({ version: 1, cards: data.cards }),
      );
    } catch {
      /* ignore */
    }
  }, { bookId: BOOK_ID, cards });
}

async function selectInSid(page: Page, sid: string) {
  await page.evaluate((s) => {
    const el = document.querySelector(`[data-sid="${s}"]`) as HTMLElement;
    const text = el?.firstChild;
    if (!text) return;
    const range = document.createRange();
    range.setStart(text, 0);
    range.setEnd(text, 5);
    const sel = window.getSelection()!;
    sel.removeAllRanges();
    sel.addRange(range);
    document.dispatchEvent(new Event("selectionchange"));
  }, sid);
}

test.describe("Slice R1b — fit-and-finish", () => {
  test.beforeEach(async ({ page }) => {
    await page.addInitScript(() => {
      try { window.localStorage.clear(); } catch { /* ignore */ }
    });
  });

  // AC1: BookSpread has fixed outer width and min-height.
  // Turning between spreads produces zero measurable change in width.
  test("AC1 fixed spread dimensions across page turns", async ({ page }) => {
    const TOTAL = 3;
    await mockBooks(page, TOTAL);
    for (let i = 1; i <= TOTAL; i++) {
      await mockChapter(page, i, TOTAL, LONG_SIDS);
    }

    await page.goto(`/books/${BOOK_ID}/read/1`);
    await expect(page.getByTestId("book-spread")).toBeVisible();

    const spread = page.locator(".rr-book");
    const box0 = await spread.boundingBox();
    expect(box0).not.toBeNull();
    const w0 = box0!.width;
    const h0 = box0!.height;

    // Turn to next spread.
    await page.keyboard.press("ArrowRight");
    // Either same chapter spread 1 or ch2 spread 0.
    await page.waitForTimeout(300);
    await expect(page.getByTestId("book-spread")).toBeVisible();

    const box1 = await spread.boundingBox();
    expect(box1).not.toBeNull();
    expect(box1!.width).toBe(w0);
    expect(box1!.height).toBeGreaterThanOrEqual(h0);
  });

  // AC2: only current-spread cards render; cross-spread cards do not.
  test("AC2 only current-spread cards render", async ({ page }) => {
    const TOTAL = 1;
    await mockBooks(page, TOTAL);
    // Large chapter so we get 2+ spreads.
    await mockChapter(page, 1, TOTAL, LONG_SIDS);
    await mockQuery(page);

    await page.goto(`/books/${BOOK_ID}/read/1`);
    await expect(page.getByTestId("book-spread")).toBeVisible();

    // Ask about a sentence on spread 0 (p1.s1).
    await selectInSid(page, "p1.s1");
    await page.getByRole("button", { name: "Ask" }).click();
    await expect(page.getByTestId("ask-answer").first()).toContainText(
      "Synthesized answer",
      { timeout: 5000 },
    );
    // Card is visible on spread 0.
    await expect(page.getByTestId("margin-column")).toContainText("Synthesized answer");

    // Turn to spread 1.
    await page.keyboard.press("ArrowRight");
    await page.waitForTimeout(200);

    // Card anchored to spread-0 sid should NOT appear on spread 1.
    await expect(page.getByTestId("margin-column")).not.toContainText("Synthesized answer");
  });

  // AC3: ArrowRight advances to next chapter at end.
  test("AC3 arrow-right advances to next chapter at end", async ({ page }) => {
    const TOTAL = 3;
    await mockBooks(page, TOTAL);
    // Each chapter fits on 1 spread.
    for (let i = 1; i <= TOTAL; i++) {
      await mockChapter(page, i, TOTAL, SHORT_SIDS);
    }

    await page.goto(`/books/${BOOK_ID}/read/1`);
    await expect(page.getByTestId("book-spread")).toBeVisible();

    // Ch1 → Ch2.
    await page.keyboard.press("ArrowRight");
    await expect(page).toHaveURL(new RegExp(`/read/2`), { timeout: 3000 });
    await expect(page.getByTestId("book-spread")).toBeVisible();

    // Ch2 → Ch3.
    await page.keyboard.press("ArrowRight");
    await expect(page).toHaveURL(new RegExp(`/read/3`), { timeout: 3000 });
    await expect(page.getByTestId("book-spread")).toBeVisible();

    // Ch3 (last) → no-op.
    await page.keyboard.press("ArrowRight");
    await page.waitForTimeout(300);
    await expect(page).toHaveURL(new RegExp(`/read/3`));
  });

  // AC4: ArrowLeft returns to previous chapter last spread.
  test("AC4 arrow-left returns to previous chapter last spread", async ({ page }) => {
    const TOTAL = 3;
    await mockBooks(page, TOTAL);
    for (let i = 1; i <= TOTAL; i++) {
      // Ch1 gets long sids so it has multiple spreads; others are short.
      const sids = i === 1 ? LONG_SIDS : SHORT_SIDS;
      await mockChapter(page, i, TOTAL, sids);
    }

    await page.goto(`/books/${BOOK_ID}/read/2`);
    await expect(page.getByTestId("book-spread")).toBeVisible();

    // Ch2 spread 0 → ch1 last spread.
    await page.keyboard.press("ArrowLeft");
    await expect(page).toHaveURL(new RegExp(`/read/1`), { timeout: 3000 });
    await expect(page.getByTestId("book-spread")).toBeVisible();

    // The counter should read N / N (last spread), e.g. "2 / 2" or "> 1 /".
    const counter = page.locator("[aria-hidden='true']").filter({ hasText: "/" });
    const counterText = await counter.first().textContent();
    if (counterText) {
      const [cur, tot] = counterText.split("/").map((s) => s.trim());
      // cur should equal tot (we're on the last spread).
      expect(cur).toBe(tot);
    }

    // ArrowLeft on ch1 spread 0 → no-op.
    // First navigate to ch1 spread 0 using ArrowLeft multiple times or directly.
    // Reload ch1 at spread 0.
    await page.goto(`/books/${BOOK_ID}/read/1`);
    await expect(page.getByTestId("book-spread")).toBeVisible();
    await page.keyboard.press("ArrowLeft");
    await page.waitForTimeout(300);
    await expect(page).toHaveURL(new RegExp(`/read/1`));
  });

  // AC5: R3 S7 cross-page prefix still fires intra-spread (left page anchor).
  test("AC5 R3 S7 cross-page prefix fires for left-page anchor within spread", async ({
    page,
  }) => {
    const TOTAL = 1;
    await mockBooks(page, TOTAL);
    await mockChapter(page, 1, TOTAL, LONG_SIDS);
    await mockQuery(page);

    await page.goto(`/books/${BOOK_ID}/read/1`);
    await expect(page.getByTestId("book-spread")).toBeVisible();

    // Ask about p1.s1 which should be on the left page of spread 0.
    await selectInSid(page, "p1.s1");
    await page.getByRole("button", { name: "Ask" }).click();
    await expect(page.getByTestId("ask-answer").first()).toContainText(
      "Synthesized answer",
      { timeout: 5000 },
    );

    // The margin column is on the right side; if the card anchor is on the
    // left page, the "← FROM p. 1 ·" cross-page prefix should be visible.
    const prefix = page.locator("text=← FROM p. 1 ·");
    await expect(prefix).toBeVisible({ timeout: 3000 });
  });
});
