import { test, expect } from "@playwright/test";
import type { Page, Route } from "@playwright/test";

const BOOK_ID = "christmas_carol_e6ddcd76";

async function mockReadingBackend(page: Page) {
  await page.route("http://localhost:8000/books", async (route: Route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify([
        {
          book_id: BOOK_ID,
          title: "Christmas Carol",
          total_chapters: 3,
          current_chapter: 2,
          ready_for_query: true,
        },
      ]),
    });
  });
  await page.route(
    `http://localhost:8000/books/${BOOK_ID}/chapters`,
    async (route: Route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify([
          { num: 1, title: "Chapter 1", word_count: 3000 },
          { num: 2, title: "The Last of the Spirits", word_count: 2000 },
          { num: 3, title: "Chapter 3", word_count: 500 },
        ]),
      });
    }
  );
  await page.route(
    new RegExp(
      `^http://localhost:8000/books/${BOOK_ID}/chapters/(\\d+)$`
    ),
    async (route: Route) => {
      const url = route.request().url();
      const n = Number.parseInt(url.split("/").pop() ?? "1", 10);
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          num: n,
          title: n === 2 ? "The Last of the Spirits" : `Chapter ${n}`,
          paragraphs: [
            `Opening paragraph of chapter ${n}.`,
            `Second paragraph of chapter ${n}.`,
          ],
          has_prev: n > 1,
          has_next: n < 3,
          total_chapters: 3,
        }),
      });
    }
  );
}

test.describe("chat flow (hermetic)", () => {
  // Margin Marks: chat lives inside the panel's Thread tab. The rail is
  // collapsed by default; click Thread to expand the panel first.
  async function openThread(page: import("@playwright/test").Page) {
    await page.getByRole("button", { name: /^thread$/i }).click();
  }

  test("empty state is visible after opening the Thread tab", async ({ page }) => {
    await mockReadingBackend(page);
    await page.goto(`/books/${BOOK_ID}/read/2`);
    await expect(
      page.getByText(/opening paragraph of chapter 2/i)
    ).toBeVisible();
    await openThread(page);
    await expect(
      page.getByText(/ask about what you've read\./i)
    ).toBeVisible();
  });

  test("typing a question and pressing Enter renders user bubble + thinking, then a successful response with a source", async ({
    page,
  }) => {
    await mockReadingBackend(page);

    // Delayed query response so we can observe the thinking state
    let bodySent: unknown = null;
    await page.route(
      `http://localhost:8000/books/${BOOK_ID}/query`,
      async (route: Route) => {
        bodySent = JSON.parse(route.request().postData() ?? "{}");
        await new Promise((r) => setTimeout(r, 300));
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({
            book_id: BOOK_ID,
            question: "Who is Marley?",
            search_type: "GRAPH_COMPLETION",
            current_chapter: 2,
            // GraphRAG synthesis: LLM answer in the bubble, raw sources below.
            answer:
              "Marley is Scrooge's deceased business partner whose ghost visits to warn him.",
            results: [
              {
                content: "Marley is Scrooge's dead business partner.",
                entity_type: "Character",
                chapter: 1,
              },
            ],
            result_count: 1,
          }),
        });
      }
    );

    await page.goto(`/books/${BOOK_ID}/read/2`);
    await expect(
      page.getByText(/opening paragraph of chapter 2/i)
    ).toBeVisible();
    await openThread(page);

    const input = page.getByLabel(/ask about what you've read/i);
    await input.fill("Who is Marley?");
    await input.press("Enter");

    // User bubble shows
    await expect(page.getByText("Who is Marley?")).toBeVisible();
    // Thinking bubble is visible while the request is in flight
    await expect(page.getByText(/thinking…/i)).toBeVisible();
    // Response lands: synthesized answer appears in the assistant bubble,
    // raw source card below.
    await expect(
      page.getByText(/whose ghost visits to warn him/i)
    ).toBeVisible();
    await expect(page.getByText(/marley is scrooge's dead business partner/i).first()).toBeVisible();
    await expect(page.getByText("Ch. 1")).toBeVisible();
    // Thinking has been replaced
    await expect(page.getByText(/thinking…/i)).toHaveCount(0);
    // The request carried max_chapter == current_chapter (2)
    expect(bodySent).toMatchObject({
      question: "Who is Marley?",
      search_type: "GRAPH_COMPLETION",
      max_chapter: 2,
    });
  });

  test("empty results render the read-so-far fallback", async ({ page }) => {
    await mockReadingBackend(page);
    await page.route(
      `http://localhost:8000/books/${BOOK_ID}/query`,
      async (route: Route) => {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({
            book_id: BOOK_ID,
            question: "obscure",
            search_type: "GRAPH_COMPLETION",
            current_chapter: 2,
            results: [],
            result_count: 0,
          }),
        });
      }
    );

    await page.goto(`/books/${BOOK_ID}/read/2`);
    await expect(
      page.getByText(/opening paragraph of chapter 2/i)
    ).toBeVisible();
    await openThread(page);

    const input = page.getByLabel(/ask about what you've read/i);
    await input.fill("obscure question");
    await input.press("Enter");

    await expect(
      page.getByText(/i don't have anything in your read-so-far/i)
    ).toBeVisible();
  });

  test("429 renders 'Too many requests, slow down.'", async ({ page }) => {
    await mockReadingBackend(page);
    await page.route(
      `http://localhost:8000/books/${BOOK_ID}/query`,
      async (route: Route) => {
        await route.fulfill({
          status: 429,
          contentType: "application/json",
          body: JSON.stringify({ detail: "rate-limited" }),
        });
      }
    );

    await page.goto(`/books/${BOOK_ID}/read/2`);
    await expect(
      page.getByText(/opening paragraph of chapter 2/i)
    ).toBeVisible();
    await openThread(page);

    const input = page.getByLabel(/ask about what you've read/i);
    await input.fill("Hello");
    await input.press("Enter");

    await expect(
      page.getByText(/too many requests, slow down\./i)
    ).toBeVisible();
  });
});
