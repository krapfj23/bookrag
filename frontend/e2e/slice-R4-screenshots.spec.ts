import { test, type Page, type Route } from "@playwright/test";
import path from "node:path";

const BOOK_ID = "carol";
const ASSETS_DIR = path.resolve(
  process.cwd(),
  "../docs/superpowers/reviews/assets/2026-04-22-slice-R4",
);

function shot(page: Page, name: string) {
  return page.screenshot({ path: path.join(ASSETS_DIR, name), fullPage: true });
}

function makeChapter(n: number, total = 5) {
  const sentences = [
    { sid: "p1.s1", text: "Alpha sentence padded with more words for selection." },
    { sid: "p1.s2", text: "Bravo sentence padded with more words for selection." },
    { sid: "p1.s3", text: "Gamma sentence padded with more words for selection." },
  ];
  const paragraphs_anchored = [{ paragraph_idx: 1, sentences }];
  const paragraphs = paragraphs_anchored.map((p) =>
    p.sentences.map((s) => s.text).join(" "),
  );
  return {
    num: n,
    title: `Chapter ${n}`,
    total_chapters: total,
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
          total_chapters: 5,
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
}

test.describe("Slice R4 — screenshots", () => {
  test("off then on", async ({ page }) => {
    await mockAll(page);
    await page.goto(`/books/${BOOK_ID}/read/1`);
    await page.waitForSelector('[data-testid="book-spread"]');
    await shot(page, "reading-mode-off.png");
    await page.getByRole("button", { name: "Reading mode" }).click();
    await page.waitForTimeout(500);
    await shot(page, "reading-mode-on.png");
  });
});
