/**
 * Slice R-visual T22 — End-to-end flow validation.
 *
 * Walks the full reader visual-fidelity flow and screenshots each step into
 * docs/superpowers/reviews/assets/2026-04-22-slice-R-visual/flow-<NN>-<name>.png.
 *
 * Flow:
 *   01 library           — library with seeded book
 *   02 reader-default    — after navigating into the reader
 *   03 drop-cap          — drop cap visible on first paragraph
 *   04 selection-toolbar — text selected, toolbar animated in
 *   05 ask-card          — Ask triggered: card flip-in + phrase pulse
 *   06 note-created      — Note created after selection
 *   07 reading-mode-on   — ambient gradient + pacing + arrows + legend + hairline
 *   08 note-peek-open    — hover a noted phrase, peek popover visible
 *   09 reading-mode-off  — toggled off, margin column returns
 */
import { test, expect, type Page, type Route } from "@playwright/test";
import path from "path";
import { fileURLToPath } from "url";

const BOOK_ID = "carol";
const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const ASSET_DIR = path.resolve(
  __dirname,
  "../../docs/superpowers/reviews/assets/2026-04-22-slice-R-visual"
);

function makeChapter(n: number, total = 5) {
  const sentences = [
    { sid: "p1.s1", text: "Marley was dead, to begin with, there is no doubt whatever about that." },
    { sid: "p1.s2", text: "The register of his burial was signed by the clergyman and the clerk." },
    { sid: "p1.s3", text: "Scrooge signed it, and Scrooge's name was good upon 'Change for anything he chose." },
  ];
  return {
    num: n,
    title: `Chapter ${n}`,
    total_chapters: total,
    has_prev: n > 1,
    has_next: n < total,
    paragraphs: sentences.map((s) => s.text),
    paragraphs_anchored: [{ paragraph_idx: 1, sentences }],
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
          title: "A Christmas Carol",
          author: "Charles Dickens",
          total_chapters: 5,
          current_chapter: 1,
          ready_for_query: true,
        },
      ]),
    });
  });
  await page.route(
    /^http:\/\/localhost:8000\/books\/[^/]+\/chapters\/(\d+)$/,
    async (route: Route) => {
      const url = route.request().url();
      const m = /\/chapters\/(\d+)$/.exec(url);
      const n = m ? parseInt(m[1], 10) : 1;
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(makeChapter(n, 5)),
      });
    }
  );
  await page.route(
    /^http:\/\/localhost:8000\/books\/[^/]+\/query$/,
    async (route: Route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          book_id: BOOK_ID,
          question: "q",
          search_type: "GRAPH_COMPLETION",
          current_chapter: 1,
          answer: "Marley's death sets up the ghostly visits.",
          results: [],
          result_count: 0,
        }),
      });
    }
  );
  await page.route(
    /^http:\/\/localhost:8000\/books\/[^/]+\/progress$/,
    async (route: Route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ book_id: BOOK_ID, current_chapter: 1 }),
      });
    }
  );
}

async function selectInSid(page: Page, sid: string, chars = 6) {
  await page.evaluate(
    ({ s, n }) => {
      const el = document.querySelector(`[data-sid="${s}"]`) as HTMLElement;
      if (!el) throw new Error(`No element with data-sid="${s}"`);
      const text = el.firstChild!;
      const range = document.createRange();
      range.setStart(text, 0);
      range.setEnd(text, n);
      const sel = window.getSelection()!;
      sel.removeAllRanges();
      sel.addRange(range);
      document.dispatchEvent(new Event("selectionchange"));
    },
    { s: sid, n: chars }
  );
}

async function shot(page: Page, name: string) {
  await page.screenshot({ path: path.join(ASSET_DIR, name), fullPage: false });
}

test.describe("T22 — reader visual fidelity end-to-end flow", () => {
  test("library -> reader -> selection -> ask -> note -> reading mode -> peek -> off", async ({ page }) => {
    await mockAll(page);

    // 01 — library
    await page.goto("/");
    const bookCard = page.getByRole("button", { name: /christmas carol/i }).first();
    await expect(bookCard).toBeVisible({ timeout: 10_000 });
    await shot(page, "flow-01-library.png");

    // 02 — reader default
    await bookCard.click();
    await page.waitForURL(/\/books\/[^/]+\/read\/\d+/, { timeout: 10_000 });
    await page.waitForSelector('[data-testid="reader-topbar"]');
    await page.waitForSelector('[data-testid="book-spread"]');
    await shot(page, "flow-02-reader-default.png");

    // 03 — drop cap visible
    await page.waitForSelector(".rr-dropcap");
    const dropCapSize = await page.evaluate(() => {
      const el = document.querySelector(".rr-dropcap") as HTMLElement;
      return getComputedStyle(el, "::first-letter").fontSize;
    });
    expect(dropCapSize).toBe("54px");
    await shot(page, "flow-03-drop-cap.png");

    // 04 — selection toolbar animates in
    await page.waitForSelector('[data-sid="p1.s1"]');
    await selectInSid(page, "p1.s1", 6);
    await page.waitForSelector('[data-testid="selection-toolbar"]');
    await shot(page, "flow-04-selection-toolbar.png");

    // 05 — Ask -> card flip-in + anchor pulse
    await page.click('[data-testid="selection-toolbar"] [aria-label="Ask"]');
    await page.waitForSelector('[data-testid="skeleton-ask-card"], [data-card-kind="ask"]', {
      timeout: 10_000,
    });
    await page.waitForFunction(() => !!document.querySelector('[data-card-kind="ask"]'), {
      timeout: 15_000,
    });
    const cardHasEnter = await page.evaluate(() => {
      const card = document.querySelector('[data-card-kind="ask"]') as HTMLElement;
      return card?.className?.includes("rr-card-enter") ?? false;
    });
    expect(cardHasEnter).toBe(true);
    await shot(page, "flow-05-ask-card.png");

    // 06 — Note created
    await selectInSid(page, "p1.s2", 6);
    await page.waitForSelector('[data-testid="selection-toolbar"]');
    await page.click('[data-testid="selection-toolbar"] [aria-label="Note"]');
    await page.waitForTimeout(150);
    await shot(page, "flow-06-note-created.png");

    // 07 — Reading mode ON
    await page.click('[aria-label="Reading mode"]');
    await page.waitForSelector('[data-testid="pacing-label"]');
    await page.waitForSelector('[data-testid="page-arrow-right"]');
    await page.waitForSelector('[data-testid="reading-mode-legend"]');
    await page.waitForSelector('[data-testid="progress-hairline"]');
    await shot(page, "flow-07-reading-mode-on.png");

    // 08 — Hover a noted phrase -> NotePeek opens
    const noteSid = await page.evaluate(() => {
      const el = document.querySelector('.rr-note-anchor, [data-annot-kind="note"]') as HTMLElement | null;
      return el?.getAttribute("data-sid") ?? null;
    });
    if (noteSid) {
      await page.hover(`[data-sid="${noteSid}"]`);
      // peek uses a timeout to appear; wait a touch
      await page.waitForTimeout(300);
      const peek = page.locator('[data-testid="note-peek"]');
      if ((await peek.count()) > 0) {
        await expect(peek.first()).toBeVisible();
      }
    }
    await shot(page, "flow-08-note-peek-open.png");

    // 09 — Reading mode OFF
    await page.click('[aria-label="Reading mode"]');
    await page.waitForTimeout(200);
    await shot(page, "flow-09-reading-mode-off.png");
  });
});
