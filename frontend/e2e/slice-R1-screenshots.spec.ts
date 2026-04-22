import { test, expect } from "@playwright/test";
import type { Page, Route } from "@playwright/test";

const BOOK_ID = "carol";
const OUT = "../docs/superpowers/reviews/assets/2026-04-22-slice-R1";

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

async function mockAll(page: Page) {
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

test.describe("R1 acceptance-criterion screenshots", () => {
  test.beforeEach(async ({ page }) => {
    await mockAll(page);
  });

  test("AC1: two-page spread renders", async ({ page }) => {
    await page.goto(`/books/${BOOK_ID}/read/1`);
    await expect(page.getByTestId("book-spread")).toBeVisible();
    await page.screenshot({ path: `${OUT}/ac1-two-page-spread.png`, fullPage: true });
  });

  test("AC4/AC9/AC12: initial cursor + fog-of-war", async ({ page }) => {
    await page.goto(`/books/${BOOK_ID}/read/1`);
    await expect(page.locator('[data-sid="p1.s1"]')).toBeVisible();
    await page.screenshot({ path: `${OUT}/ac9-fog-of-war.png`, fullPage: true });
  });

  test("AC8/AC10: ArrowRight advances spread and cursor", async ({ page }) => {
    await page.goto(`/books/${BOOK_ID}/read/1`);
    await expect(page.getByTestId("book-spread")).toBeVisible();
    await page.keyboard.press("ArrowRight");
    await page.waitForTimeout(200);
    await page.screenshot({ path: `${OUT}/ac10-after-arrow-right.png`, fullPage: true });
  });

  test("AC11: cursor persists across reload", async ({ page }) => {
    await page.goto(`/books/${BOOK_ID}/read/1`);
    await expect(page.getByTestId("book-spread")).toBeVisible();
    await page.keyboard.press("ArrowRight");
    await page.reload();
    await expect(page.getByTestId("book-spread")).toBeVisible();
    await page.screenshot({ path: `${OUT}/ac11-cursor-persisted.png`, fullPage: true });
  });

  test("AC7: sentences carry data-sid attributes", async ({ page }) => {
    await page.goto(`/books/${BOOK_ID}/read/1`);
    await expect(page.locator('[data-sid="p1.s1"]')).toBeVisible();
    // Draw an outline around every data-sid element to visualize anchors.
    await page.addStyleTag({
      content: `[data-sid] { outline: 1px dashed rgba(255,0,0,0.4); }`,
    });
    await page.screenshot({ path: `${OUT}/ac7-data-sid-anchors.png`, fullPage: true });
  });
});
