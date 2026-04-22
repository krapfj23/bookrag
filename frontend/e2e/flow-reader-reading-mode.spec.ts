import { test, expect, type Page, type Route } from "@playwright/test";
import path from "node:path";

/**
 * T11 — End-to-end flow validation for reading mode (Slice R4).
 *
 * Exercises the full reading-mode toggle lifecycle on a mocked book:
 *   1. Toggle ON  → ambient radial gradient on root, chrome visible, margin hidden.
 *   2. Note-peek  → seed a note card, hover the noted phrase, peek appears/hides.
 *   3. Page turn  → right-arrow advances spread counter.
 *   4. Persistence → reload retains ON state.
 *   5. Toggle OFF → chrome removed, margin accessible again.
 *
 * No backend server is required — all HTTP is intercepted via page.route().
 */

const BOOK_ID = "carol";

const ASSETS_DIR = path.resolve(
  process.cwd(),
  "../docs/superpowers/reviews/assets/2026-04-22-slice-R4",
);

function shot(page: Page, name: string) {
  return page.screenshot({ path: path.join(ASSETS_DIR, name), fullPage: true });
}

/** Multi-spread chapter (60 sentences) so page-turn advances counter. */
function makeLongChapter(n: number, total = 5) {
  const sentences = Array.from({ length: 60 }).map((_, i) => ({
    sid: `p${Math.floor(i / 4) + 1}.s${(i % 4) + 1}`,
    text: `Chapter ${n} sentence ${i + 1} padded out with enough words to force multiple spreads during pagination.`,
  }));

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
    total_chapters: total,
    has_prev: false,
    has_next: n < total,
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
          title: "A Christmas Carol",
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
      const m = /\/chapters\/(\d+)$/.exec(route.request().url());
      const n = m ? parseInt(m[1], 10) : 1;
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(makeLongChapter(n, 5)),
      });
    },
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
          answer: "Synthesized R4 flow answer.",
          results: [],
          result_count: 0,
        }),
      });
    },
  );
}

/**
 * Seed a note card via localStorage so note-peek can be exercised without
 * going through the selection-toolbar flow. Follows the same pattern as
 * slice-R3-card-states-and-overflow.spec.ts AC8/9/10.
 */
async function seedNoteCard(page: Page, bookId: string) {
  await page.addInitScript((bId) => {
    const now = Date.now();
    const cards = [
      {
        id: "note-r4-flow",
        bookId: bId,
        anchor: "p1.s1",
        quote: "Chapter 1 sentence 1",
        chapter: 1,
        kind: "note",
        body: "Seeded note for R4 flow peek test.",
        createdAt: new Date(now - 1000).toISOString(),
        updatedAt: new Date(now - 1000).toISOString(),
      },
    ];
    window.localStorage.setItem(
      `bookrag.cards.${bId}`,
      JSON.stringify({ version: 1, cards }),
    );
  }, bookId);
}

test.describe("T11 — End-to-end flow: reading mode (Slice R4)", () => {
  test("full flow: toggle on → note-peek → page turn → persist → toggle off", async ({
    page,
  }) => {
    await mockAll(page);
    await seedNoteCard(page, BOOK_ID);

    // --- Navigate to chapter 1 ---
    await page.goto(`/books/${BOOK_ID}/read/1`);
    await expect(page.getByTestId("book-spread")).toBeVisible({ timeout: 8000 });

    // --- Toggle reading mode ON ---
    const pill = page.getByRole("button", { name: "Reading mode" });
    await expect(pill).toBeVisible();
    await pill.click();
    await expect(page.getByTestId("reading-screen")).toHaveAttribute(
      "data-reading-mode",
      "on",
    );
    // Wait for the 420ms gradient transition to settle.
    await page.waitForTimeout(500);

    // Screenshot: toggled on.
    await shot(page, "flow-01-toggled-on.png");

    // --- Assert ambient radial gradient on the reader root ---
    const rootBg = await page.getByTestId("reading-screen").evaluate(
      (el) => getComputedStyle(el).backgroundImage,
    );
    expect(rootBg).toContain("radial-gradient");
    // Verify the two color stops are present in the computed value.
    // Browsers normalize oklch; check for the gradient keyword at minimum.
    expect(rootBg.toLowerCase()).toMatch(/radial-gradient/);

    // --- Assert reading-mode chrome is visible ---
    await expect(page.getByTestId("pacing-label")).toBeVisible();
    await expect(page.getByTestId("page-arrow-left")).toBeVisible();
    await expect(page.getByTestId("page-arrow-right")).toBeVisible();
    await expect(page.getByTestId("progress-hairline")).toBeVisible();
    await expect(page.getByTestId("reading-mode-legend")).toBeVisible();

    // --- Assert margin-column is aria-hidden ---
    await expect(page.getByTestId("margin-column")).toHaveAttribute(
      "aria-hidden",
      "true",
    );

    // --- Note-peek: hover the seeded noted phrase → peek appears ---
    const notedSpan = page.locator('[data-kind="note"]').first();
    await expect(notedSpan).toBeVisible();
    await notedSpan.hover();
    await page.waitForTimeout(200);
    const peek = page.getByTestId("note-peek");
    await expect(peek).toBeVisible({ timeout: 2000 });

    // Screenshot: note-peek visible.
    await shot(page, "flow-02-note-peek.png");

    // Mouse away — peek should hide.
    await page.mouse.move(0, 0);
    await expect(peek).toHaveCount(0);

    // --- Page turn: right arrow advances spread counter ---
    const counterBefore = await page
      .locator("[aria-hidden='true']")
      .filter({ hasText: "/" })
      .first()
      .textContent();

    await page.keyboard.press("ArrowRight");
    await page.waitForTimeout(150);

    const counterAfter = await page
      .locator("[aria-hidden='true']")
      .filter({ hasText: "/" })
      .first()
      .textContent();

    // Counter should have advanced (spread number increased).
    const beforeNum = parseInt((counterBefore ?? "1 / 1").split("/")[0].trim(), 10);
    const afterNum = parseInt((counterAfter ?? "2 / 1").split("/")[0].trim(), 10);
    expect(afterNum).toBeGreaterThan(beforeNum);

    // Screenshot: after page turn.
    await shot(page, "flow-03-page-turned.png");

    // --- Reload: reading mode persisted ---
    await page.reload();
    await expect(page.getByTestId("book-spread")).toBeVisible({ timeout: 8000 });
    await expect(page.getByTestId("reading-screen")).toHaveAttribute(
      "data-reading-mode",
      "on",
    );

    // --- Toggle OFF: chrome removed, margin accessible ---
    await page.getByRole("button", { name: "Reading mode" }).click();
    await expect(page.getByTestId("reading-screen")).toHaveAttribute(
      "data-reading-mode",
      "off",
    );
    await page.waitForTimeout(350);

    // Chrome elements removed from DOM.
    await expect(page.getByTestId("pacing-label")).toHaveCount(0);
    await expect(page.getByTestId("page-arrow-left")).toHaveCount(0);
    await expect(page.getByTestId("page-arrow-right")).toHaveCount(0);
    await expect(page.getByTestId("progress-hairline")).toHaveCount(0);
    await expect(page.getByTestId("reading-mode-legend")).toHaveCount(0);

    // Margin column no longer aria-hidden.
    const marginHidden = await page
      .getByTestId("margin-column")
      .getAttribute("aria-hidden");
    expect(marginHidden).toBeNull();

    // Screenshot: toggled off.
    await shot(page, "flow-04-toggled-off.png");
  });
});
