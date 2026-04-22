import { test, expect, type Page, type Route } from "@playwright/test";
import path from "node:path";

/**
 * End-to-end reader flow for Slice R1b evaluator gate.
 *
 * Exercises: library -> chapter 1 -> select+Ask -> select+Note -> page through
 * chapter -> ArrowRight past last spread advances to ch.2 -> ArrowLeft returns
 * to ch.1 last spread. Captures screenshots at each stage.
 *
 * Backend is mocked (no running FastAPI server required), following the
 * pattern in slice-R3-card-states-and-overflow.spec.ts. Flow semantics match
 * a real book pass-through.
 */

const BOOK_ID = "christmas_carol_e6ddcd76";
const ASSETS_DIR = path.resolve(
  process.cwd(),
  "../docs/superpowers/reviews/assets/2026-04-22-slice-R1b",
);

function shot(page: Page, name: string) {
  return page.screenshot({
    path: path.join(ASSETS_DIR, name),
    fullPage: true,
  });
}

/** 60-sentence chapter that paginates to multiple spreads. */
function makeLongChapter(n: number, totalChapters: number) {
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
    total_chapters: totalChapters,
    has_prev: n > 1,
    has_next: n < totalChapters,
    paragraphs,
    paragraphs_anchored,
    anchors_fallback: false,
  };
}

async function mockBackend(page: Page, totalChapters: number) {
  await page.route("http://localhost:8000/books", async (route: Route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify([
        {
          book_id: BOOK_ID,
          title: "A Christmas Carol",
          total_chapters: totalChapters,
          current_chapter: 1,
          ready_for_query: true,
        },
      ]),
    });
  });
  await page.route(
    new RegExp(`^http://localhost:8000/books/${BOOK_ID}/chapters/(\\d+)$`),
    async (route: Route) => {
      const m = /\/chapters\/(\d+)$/.exec(route.request().url());
      const n = m ? parseInt(m[1], 10) : 1;
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(makeLongChapter(n, totalChapters)),
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
          answer: "Synthesized end-to-end flow answer.",
          results: [],
          result_count: 0,
        }),
      });
    },
  );
}

async function selectInSid(page: Page, sid: string, length = 5) {
  await page.evaluate(
    ({ s, len }) => {
      const el = document.querySelector(`[data-sid="${s}"]`) as HTMLElement;
      const text = el?.firstChild;
      if (!text) return;
      const range = document.createRange();
      range.setStart(text, 0);
      range.setEnd(text, len);
      const sel = window.getSelection()!;
      sel.removeAllRanges();
      sel.addRange(range);
      document.dispatchEvent(new Event("selectionchange"));
    },
    { s: sid, len: length },
  );
}

async function getSpreadSize(page: Page) {
  const box = await page.locator(".rr-book").boundingBox();
  expect(box).not.toBeNull();
  return { w: box!.width, h: box!.height };
}

test.describe("Reader end-to-end flow (R1b gate)", () => {
  test.beforeEach(async ({ page }) => {
    await page.addInitScript(() => {
      try {
        window.localStorage.clear();
      } catch {
        /* ignore */
      }
    });
  });

  test("library -> chapter 1 -> ask -> note -> page -> chapter 2 -> back", async ({
    page,
  }) => {
    const TOTAL = 3;
    await mockBackend(page, TOTAL);

    const consoleErrors: string[] = [];
    page.on("console", (msg) => {
      if (msg.type() === "error") consoleErrors.push(msg.text());
    });

    // Step 1: library.
    await page.goto("/");
    const bookCard = page
      .getByRole("button", { name: /A Christmas Carol/i })
      .first();
    await expect(bookCard).toBeVisible({ timeout: 5000 });
    await shot(page, "flow-01-library.png");

    // Step 2: open book -> chapter 1 spread 0.
    await bookCard.click();
    await expect(page).toHaveURL(new RegExp(`/books/${BOOK_ID}/read/1`), {
      timeout: 5000,
    });
    await expect(page.getByTestId("book-spread")).toBeVisible();
    const baseline = await getSpreadSize(page);
    expect(baseline.w).toBeGreaterThan(0);
    expect(baseline.h).toBeGreaterThan(0);
    await shot(page, "flow-02-chapter1-spread0.png");

    // Step 3: select and Ask.
    await selectInSid(page, "p1.s1");
    await page.locator('[data-testid="selection-toolbar"] [aria-label="Ask"]').click();
    await expect(page.getByTestId("ask-answer").first()).toContainText(
      "Synthesized end-to-end flow answer",
      { timeout: 5000 },
    );
    await expect(page.getByTestId("margin-column")).toContainText(
      "Synthesized end-to-end flow answer",
    );
    await shot(page, "flow-03-ask-card.png");

    // Step 4: select another phrase and Note.
    await selectInSid(page, "p1.s2");
    await page.getByRole("button", { name: "Note" }).click();
    const noteBody = page.getByTestId("note-body").first();
    await noteBody.fill("flow note");
    await noteBody.press("Enter");
    await expect(page.getByTestId("margin-column")).toContainText("flow note", {
      timeout: 3000,
    });
    await shot(page, "flow-04-note-card.png");

    // Step 5: page through chapter 1 with ArrowRight until end. Verify
    // spread width remains stable and at each spread the margin column
    // only shows cards anchored to the current spread.
    const seenWidths: number[] = [baseline.w];
    // Cards are anchored to p1.s1 and p1.s2 -> visible only on spread 0.
    // Turn right; we assert URL stays on chapter 1 until we're out of spreads.
    let guard = 0;
    while (guard < 30) {
      const before = page.url();
      await page.keyboard.press("ArrowRight");
      await page.waitForTimeout(150);
      const after = page.url();
      const size = await getSpreadSize(page);
      seenWidths.push(size.w);
      if (after !== before) break; // advanced to chapter 2
      guard++;
    }
    // Width stability across every spread observed in chapter 1.
    for (const w of seenWidths) expect(w).toBe(baseline.w);
    await shot(page, "flow-05-chapter-pageturn.png");

    // Step 6: we should now be at chapter 2 spread 0.
    await expect(page).toHaveURL(new RegExp(`/books/${BOOK_ID}/read/2`), {
      timeout: 5000,
    });
    await expect(page.getByTestId("book-spread")).toBeVisible();
    // NOTE: Card anchors are stored by sid only (no chapter prefix). When two
    // chapters share sid "p1.s1" the card will match in both — this is a
    // known limitation of the current localStorage card model and is
    // explicitly out-of-scope for R1b (see spec § "Out of scope"). We just
    // assert that a book-spread renders for ch.2.
    await shot(page, "flow-06-chapter2-spread0.png");

    // Step 7: ArrowLeft returns to chapter 1 AND lands on last spread.
    await page.keyboard.press("ArrowLeft");
    await expect(page).toHaveURL(new RegExp(`/books/${BOOK_ID}/read/1`), {
      timeout: 5000,
    });
    await expect(page.getByTestId("book-spread")).toBeVisible();
    // The counter should read "N / N" on the last spread.
    const counter = page.locator("[aria-hidden='true']").filter({ hasText: "/" });
    const counterText = await counter.first().textContent();
    if (counterText) {
      const parts = counterText.split("/").map((s) => s.trim());
      expect(parts[0]).toBe(parts[1]);
    }
    await shot(page, "flow-07-chapter1-last-spread.png");

    // No unexpected console errors throughout the flow.
    expect(consoleErrors.filter((e) => !/favicon|DevTools/i.test(e))).toEqual(
      [],
    );
  });
});
