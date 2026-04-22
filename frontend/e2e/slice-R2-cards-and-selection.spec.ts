import { test, expect, type Page, type Route } from "@playwright/test";

const BOOK_ID = "carol";

function makeChapter(n: number) {
  const paragraphs_anchored = [
    {
      paragraph_idx: 1,
      sentences: [
        { sid: "p1.s1", text: "Alpha sentence padded with more words for selection." },
        { sid: "p1.s2", text: "Bravo sentence padded with more words for selection." },
        { sid: "p1.s3", text: "Gamma sentence padded with more words for selection." },
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
            "This is a synthesized answer with enough words to observe streaming chunks landing over time.",
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

test.describe("Slice R2 — margin cards, selection, ask, note", () => {
  test.beforeEach(async ({ page }) => {
    await mockAll(page);
  });

  test("selection shows the Ask/Note/Highlight toolbar (AC 3)", async ({ page }) => {
    await page.goto(`/books/${BOOK_ID}/read/1`);
    await expect(page.getByTestId("book-spread")).toBeVisible();
    await selectInSid(page, "p1.s1");
    await expect(page.getByTestId("selection-toolbar")).toBeVisible({
      timeout: 1000,
    });
    await expect(page.getByRole("button", { name: "Ask" })).toBeVisible();
    await expect(page.getByRole("button", { name: "Note" })).toBeVisible();
    await expect(page.getByRole("button", { name: "Highlight" })).toBeVisible();
  });

  test("Ask creates a card whose answer grows and ends non-empty (AC 5, 6)", async ({ page }) => {
    await page.goto(`/books/${BOOK_ID}/read/1`);
    await expect(page.getByTestId("book-spread")).toBeVisible();
    await selectInSid(page, "p1.s1");
    await page.getByRole("button", { name: "Ask" }).click();
    const answer = page.getByTestId("ask-answer").first();
    await expect(answer).toBeVisible();
    // Eventually the final answer lands.
    await expect(answer).toContainText("synthesized answer", { timeout: 5000 });
  });

  test("Note creates a card, accepts typed body, persists on Enter (AC 7, 12)", async ({ page }) => {
    await page.goto(`/books/${BOOK_ID}/read/1`);
    await expect(page.getByTestId("book-spread")).toBeVisible();
    await selectInSid(page, "p1.s1");
    await page.getByRole("button", { name: "Note" }).click();
    const body = page.getByTestId("note-body").first();
    await expect(body).toBeFocused();
    await body.fill("my annotation");
    await body.press("Enter");
    const stored = await page.evaluate(() =>
      window.localStorage.getItem(`bookrag.cards.${"carol"}`),
    );
    expect(stored).not.toBeNull();
    expect(stored!).toContain("my annotation");
  });

  test("reload restores cards (AC 12)", async ({ page }) => {
    await page.goto(`/books/${BOOK_ID}/read/1`);
    await expect(page.getByTestId("book-spread")).toBeVisible();
    await selectInSid(page, "p1.s2");
    await page.getByRole("button", { name: "Note" }).click();
    await page.getByTestId("note-body").first().fill("persist me");
    await page.getByTestId("note-body").first().press("Enter");
    await page.reload();
    await expect(page.getByTestId("book-spread")).toBeVisible();
    await expect(page.getByText("persist me")).toBeVisible();
  });

  test("asked sentence shows green highlight, clicking it focuses the card (AC 9, 10)", async ({ page }) => {
    await page.goto(`/books/${BOOK_ID}/read/1`);
    await expect(page.getByTestId("book-spread")).toBeVisible();
    await selectInSid(page, "p1.s1");
    await page.getByRole("button", { name: "Ask" }).click();
    // Wait for streaming to finish so the card is stable.
    await expect(page.getByTestId("ask-answer").first()).toContainText(
      "synthesized answer",
      { timeout: 5000 },
    );
    const sentence = page.locator('[data-sid="p1.s1"]').first();
    const bg = await sentence.evaluate((el) => getComputedStyle(el).backgroundColor);
    // oklch(72% 0.08 155 / 0.42) resolves to non-transparent.
    expect(bg).not.toBe("rgba(0, 0, 0, 0)");
    await sentence.click();
    const card = page.locator("[data-card-kind='ask']").first();
    await expect(card).toHaveClass(/rr-card-flash/);
  });

  test("Ask is disabled when selection is past the fog cursor (AC 13)", async ({ page }) => {
    await page.goto(`/books/${BOOK_ID}/read/1`);
    await expect(page.getByTestId("book-spread")).toBeVisible();
    // Initial cursor = p1.s1; selecting in p1.s2 is past the cursor.
    await selectInSid(page, "p1.s2");
    const ask = page.getByRole("button", { name: "Ask" });
    await expect(ask).toBeDisabled();
    // Note remains enabled.
    await expect(page.getByRole("button", { name: "Note" })).toBeEnabled();
  });
});
