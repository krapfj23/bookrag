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
