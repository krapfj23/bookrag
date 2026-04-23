import { test, expect, type Page, type Route } from "@playwright/test";

const BOOK_ID = "carol";
const BOOK_ID_B = "rising";

type Size = "small" | "large";

function makeChapter(n: number, total = 5, size: Size = "small") {
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
        {
          book_id: BOOK_ID_B,
          title: "Rising",
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
          answer: "answer body",
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

test.describe("Slice R4 — ambitious reading mode", () => {
  test("AC1 toggle pill off→on: data-state, Reading text, checkmark", async ({ page }) => {
    await mockAll(page);
    await page.goto(`/books/${BOOK_ID}/read/1`);
    await expect(page.getByTestId("book-spread")).toBeVisible();
    const pill = page.getByRole("button", { name: "Reading mode" });
    await expect(pill).toBeVisible();
    await expect(pill).toHaveAttribute("data-state", "off");
    await pill.click();
    await expect(pill).toHaveAttribute("data-state", "on");
    await expect(pill).toContainText("Reading");
    await expect(pill).toContainText("✓");
  });

  test("AC2 clicking pill toggles data-reading-mode on reader root", async ({ page }) => {
    await mockAll(page);
    await page.goto(`/books/${BOOK_ID}/read/1`);
    await expect(page.getByTestId("book-spread")).toBeVisible();
    const root = page.getByTestId("reading-screen");
    await expect(root).toHaveAttribute("data-reading-mode", "off");
    await page.getByRole("button", { name: "Reading mode" }).click();
    await expect(root).toHaveAttribute("data-reading-mode", "on");
    await page.getByRole("button", { name: "Reading mode" }).click();
    await expect(root).toHaveAttribute("data-reading-mode", "off");
  });

  test("AC3 on: margin-column is absent from the DOM", async ({ page }) => {
    // In reading mode, MarginColumn is removed from the tree entirely so the
    // two-page spread centers with equal ambient margins (see commit 2b1a0e0).
    await mockAll(page);
    await page.goto(`/books/${BOOK_ID}/read/1`);
    await expect(page.getByTestId("book-spread")).toBeVisible();
    await page.getByRole("button", { name: "Reading mode" }).click();
    await page.waitForTimeout(500);
    await expect(page.getByTestId("margin-column")).toHaveCount(0);
  });

  test("AC4 on: pacing label matches regex", async ({ page }) => {
    await mockAll(page);
    await page.goto(`/books/${BOOK_ID}/read/1`);
    await expect(page.getByTestId("book-spread")).toBeVisible();
    await page.getByRole("button", { name: "Reading mode" }).click();
    const label = page.getByTestId("pacing-label");
    await expect(label).toBeVisible();
    const text = (await label.textContent()) ?? "";
    expect(text).toMatch(
      /^stave (one|two|three|four|five|six|seven|eight|nine|ten|\d+) · of (one|two|three|four|five|six|seven|eight|nine|ten|\d+)$/i,
    );
  });

  test("AC5 on: left/right page arrows visible", async ({ page }) => {
    await mockAll(page);
    await page.goto(`/books/${BOOK_ID}/read/1`);
    await expect(page.getByTestId("book-spread")).toBeVisible();
    await page.getByRole("button", { name: "Reading mode" }).click();
    await expect(page.getByTestId("page-arrow-left")).toBeVisible();
    await expect(page.getByTestId("page-arrow-right")).toBeVisible();
  });

  test("AC6 on: progress hairline inner width is numeric %", async ({ page }) => {
    await mockAll(page);
    await page.goto(`/books/${BOOK_ID}/read/1`);
    await expect(page.getByTestId("book-spread")).toBeVisible();
    await page.getByRole("button", { name: "Reading mode" }).click();
    const hairline = page.getByTestId("progress-hairline");
    await expect(hairline).toBeVisible();
    const width = await hairline.evaluate((el) => {
      const fg = el.firstElementChild as HTMLElement | null;
      return fg ? fg.style.width : "";
    });
    expect(width).toMatch(/^\d+(\.\d+)?%$/);
  });

  test("AC7 on: legend contains ASKED, NOTED, ENTITY", async ({ page }) => {
    await mockAll(page);
    await page.goto(`/books/${BOOK_ID}/read/1`);
    await expect(page.getByTestId("book-spread")).toBeVisible();
    await page.getByRole("button", { name: "Reading mode" }).click();
    const legend = page.getByTestId("reading-mode-legend");
    await expect(legend).toBeVisible();
    await expect(legend).toContainText("ASKED");
    await expect(legend).toContainText("NOTED");
    await expect(legend).toContainText("ENTITY");
  });

  test("AC8 off: chrome absent and margin visible", async ({ page }) => {
    await mockAll(page);
    await page.goto(`/books/${BOOK_ID}/read/1`);
    await expect(page.getByTestId("book-spread")).toBeVisible();
    // Start off.
    await expect(page.getByTestId("pacing-label")).toHaveCount(0);
    await expect(page.getByTestId("page-arrow-left")).toHaveCount(0);
    await expect(page.getByTestId("page-arrow-right")).toHaveCount(0);
    await expect(page.getByTestId("progress-hairline")).toHaveCount(0);
    await expect(page.getByTestId("reading-mode-legend")).toHaveCount(0);
    const margin = page.getByTestId("margin-column");
    await expect(margin).toBeVisible();
  });

  test("AC9 reload restores per-book on-state from localStorage", async ({ page }) => {
    await mockAll(page);
    await page.goto(`/books/${BOOK_ID}/read/1`);
    await expect(page.getByTestId("book-spread")).toBeVisible();
    await page.getByRole("button", { name: "Reading mode" }).click();
    await expect(page.getByTestId("reading-screen")).toHaveAttribute(
      "data-reading-mode",
      "on",
    );
    await page.reload();
    await expect(page.getByTestId("book-spread")).toBeVisible();
    await expect(page.getByTestId("reading-screen")).toHaveAttribute(
      "data-reading-mode",
      "on",
    );
  });

  test("AC10 two books isolated", async ({ page }) => {
    await mockAll(page);
    await page.goto(`/books/${BOOK_ID}/read/1`);
    await expect(page.getByTestId("book-spread")).toBeVisible();
    await page.getByRole("button", { name: "Reading mode" }).click();
    await expect(page.getByTestId("reading-screen")).toHaveAttribute(
      "data-reading-mode",
      "on",
    );
    await page.goto(`/books/${BOOK_ID_B}/read/1`);
    await expect(page.getByTestId("book-spread")).toBeVisible();
    await expect(page.getByTestId("reading-screen")).toHaveAttribute(
      "data-reading-mode",
      "off",
    );
    await page.goto(`/books/${BOOK_ID}/read/1`);
    await expect(page.getByTestId("book-spread")).toBeVisible();
    await expect(page.getByTestId("reading-screen")).toHaveAttribute(
      "data-reading-mode",
      "on",
    );
  });

  test("AC11 on + hover data-kind=note ≥150ms → note-peek; mouseleave hides", async ({ page }) => {
    await mockAll(page);
    await page.goto(`/books/${BOOK_ID}/read/1`);
    await expect(page.getByTestId("book-spread")).toBeVisible();
    // Seed a note.
    await selectInSid(page, "p1.s1");
    await page.getByRole("button", { name: "Note" }).click();
    await page.getByTestId("note-body").first().fill("peeked body text");
    await page.getByTestId("note-body").first().press("Enter");
    // Enter reading mode.
    await page.getByRole("button", { name: "Reading mode" }).click();
    const noted = page.locator('[data-kind="note"]').first();
    await expect(noted).toBeVisible();
    await noted.hover();
    await page.waitForTimeout(200);
    const peek = page.getByTestId("note-peek");
    await expect(peek).toBeVisible();
    await expect(peek).toContainText("peeked body text");
    // Move away.
    await page.mouse.move(0, 0);
    await expect(peek).toHaveCount(0);
  });

  test("AC12 toggle twice: no residual chrome and no peek on hover", async ({ page }) => {
    await mockAll(page);
    await page.goto(`/books/${BOOK_ID}/read/1`);
    await expect(page.getByTestId("book-spread")).toBeVisible();
    // Seed a note.
    await selectInSid(page, "p1.s1");
    await page.getByRole("button", { name: "Note" }).click();
    await page.getByTestId("note-body").first().fill("should not peek");
    await page.getByTestId("note-body").first().press("Enter");
    const pill = page.getByRole("button", { name: "Reading mode" });
    await pill.click();
    await pill.click();
    await expect(page.getByTestId("pacing-label")).toHaveCount(0);
    await expect(page.getByTestId("reading-mode-legend")).toHaveCount(0);
    const noted = page.locator('[data-kind="note"]').first();
    await noted.hover();
    await page.waitForTimeout(250);
    await expect(page.getByTestId("note-peek")).toHaveCount(0);
  });
});
