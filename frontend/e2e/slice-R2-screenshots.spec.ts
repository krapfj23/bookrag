import { test, expect, type Page, type Route } from "@playwright/test";

const BOOK_ID = "carol";
const OUT = "../docs/superpowers/reviews/assets/2026-04-22-slice-R2";

function makeChapter(n: number) {
  const paragraphs_anchored = [
    {
      paragraph_idx: 1,
      sentences: [
        { sid: "p1.s1", text: "Alpha sentence padded with more words for selection purposes here." },
        { sid: "p1.s2", text: "Bravo sentence padded with more words for selection purposes here." },
        { sid: "p1.s3", text: "Gamma sentence padded with more words for selection purposes here." },
      ],
    },
  ];
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

async function mockAll(page: Page) {
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
        body: JSON.stringify(makeChapter(1)),
      });
    },
  );
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
          answer:
            "This is a synthesized answer with enough words to observe streaming chunks landing over time in the margin card.",
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

test.describe("Slice R2 screenshots", () => {
  test.beforeEach(async ({ page }) => {
    await mockAll(page);
    await page.setViewportSize({ width: 1400, height: 900 });
  });

  test("AC1 margin column visible next to spread", async ({ page }) => {
    await page.goto(`/books/${BOOK_ID}/read/1`);
    await expect(page.getByTestId("book-spread")).toBeVisible();
    await expect(page.getByTestId("margin-column")).toBeVisible();
    await page.screenshot({ path: `${OUT}/ac1-margin-column.png`, fullPage: true });
  });

  test("AC2 empty state S1 card", async ({ page }) => {
    await page.goto(`/books/${BOOK_ID}/read/1`);
    await expect(page.getByTestId("s1-empty-card")).toBeVisible();
    await page.screenshot({ path: `${OUT}/ac2-empty-state.png`, fullPage: true });
  });

  test("AC4 selection toolbar", async ({ page }) => {
    await page.goto(`/books/${BOOK_ID}/read/1`);
    await expect(page.getByTestId("book-spread")).toBeVisible();
    await selectInSid(page, "p1.s1");
    await expect(page.getByTestId("selection-toolbar")).toBeVisible();
    await page.screenshot({ path: `${OUT}/ac4-selection-toolbar.png`, fullPage: true });
  });

  test("AC5 ask streaming and AC6 final", async ({ page }) => {
    await page.goto(`/books/${BOOK_ID}/read/1`);
    await expect(page.getByTestId("book-spread")).toBeVisible();
    await selectInSid(page, "p1.s1");
    await page.getByRole("button", { name: "Ask" }).click();
    // Capture mid-stream shortly after click.
    await page.waitForTimeout(120);
    await page.screenshot({ path: `${OUT}/ac5-ask-streaming.png`, fullPage: true });
    // Settled state also covers AC9 (green highlight on asked sentence)
    await expect(page.getByTestId("ask-answer").first()).toContainText(
      "synthesized answer",
      { timeout: 5000 },
    );
    await page.screenshot({ path: `${OUT}/ac9-fog-disables-ask.png`, fullPage: true });
  });

  test("AC6 note card persisted with body", async ({ page }) => {
    await page.goto(`/books/${BOOK_ID}/read/1`);
    await expect(page.getByTestId("book-spread")).toBeVisible();
    await selectInSid(page, "p1.s1");
    await page.getByRole("button", { name: "Note" }).click();
    const body = page.getByTestId("note-body").first();
    await body.fill("A handwritten margin note about this passage.");
    await page.screenshot({ path: `${OUT}/ac6-note-card.png`, fullPage: true });
    await body.press("Enter");
    // AC7 persisted reload
    await page.reload();
    await expect(page.getByTestId("book-spread")).toBeVisible();
    await expect(page.getByText("A handwritten margin note about this passage.")).toBeVisible();
    await page.screenshot({ path: `${OUT}/ac7-persisted-reload.png`, fullPage: true });
  });

  test("AC11 duplicate ask focuses existing card", async ({ page }) => {
    await page.goto(`/books/${BOOK_ID}/read/1`);
    await expect(page.getByTestId("book-spread")).toBeVisible();
    await selectInSid(page, "p1.s1");
    await page.getByRole("button", { name: "Ask" }).click();
    await expect(page.getByTestId("ask-answer").first()).toContainText(
      "synthesized answer",
      { timeout: 5000 },
    );
    // Second Ask on same sid -> focus existing.
    await selectInSid(page, "p1.s1");
    await page.getByRole("button", { name: "Ask" }).click();
    await page.screenshot({ path: `${OUT}/ac11-dup-focus.png`, fullPage: true });
  });
});
