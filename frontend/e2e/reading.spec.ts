import { test, expect } from "@playwright/test";
import type { Page, Route } from "@playwright/test";

const BOOK_ID = "christmas_carol_e6ddcd76";

type Books = Array<{
  book_id: string;
  title: string;
  total_chapters: number;
  current_chapter: number;
  ready_for_query: boolean;
}>;

async function mockBooks(page: Page, current_chapter: number) {
  const books: Books = [
    {
      book_id: BOOK_ID,
      title: "Christmas Carol",
      total_chapters: 3,
      current_chapter,
      ready_for_query: true,
    },
  ];
  await page.route("http://localhost:8000/books", async (route: Route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(books),
    });
  });
}

async function mockChapters(page: Page) {
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
}

async function mockChapter(page: Page) {
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

async function mockProgress(page: Page) {
  await page.route(
    `http://localhost:8000/books/${BOOK_ID}/progress`,
    async (route: Route) => {
      const body = JSON.parse(route.request().postData() ?? "{}");
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          book_id: BOOK_ID,
          current_chapter: body.current_chapter,
        }),
      });
    }
  );
}

test.describe("reading flow (hermetic)", () => {
  test("Library → BookCard click → lands on /books/:id/read/current_chapter", async ({
    page,
  }) => {
    await mockBooks(page, 2);
    await mockChapters(page);
    await mockChapter(page);

    await page.goto("/");
    await expect(page.getByText(/your shelf/i)).toBeVisible();

    await page.getByRole("button", { name: /christmas carol/i }).click();

    await expect(page).toHaveURL(
      new RegExp(`/books/${BOOK_ID}/read/2$`)
    );
    await expect(
      page.getByText(/opening paragraph of chapter 2/i)
    ).toBeVisible();
    // Sidebar renders the three ChapterRows with current on 2
    await expect(
      page.getByRole("button", { name: /01 chapter 1/i })
    ).toBeVisible();
    await expect(
      page.getByRole("button", { name: /02 the last of the spirits/i })
    ).toBeVisible();
  });

  test("Mark as read POSTs progress and sidebar advances to the next chapter", async ({
    page,
  }) => {
    let currentChapter = 2;
    await page.route("http://localhost:8000/books", async (route: Route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify([
          {
            book_id: BOOK_ID,
            title: "Christmas Carol",
            total_chapters: 3,
            current_chapter: currentChapter,
            ready_for_query: true,
          },
        ]),
      });
    });
    await mockChapters(page);
    await mockChapter(page);
    await page.route(
      `http://localhost:8000/books/${BOOK_ID}/progress`,
      async (route: Route) => {
        const body = JSON.parse(route.request().postData() ?? "{}");
        currentChapter = body.current_chapter;
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({
            book_id: BOOK_ID,
            current_chapter: body.current_chapter,
          }),
        });
      }
    );

    await page.goto(`/books/${BOOK_ID}/read/2`);
    await expect(
      page.getByText(/opening paragraph of chapter 2/i)
    ).toBeVisible();

    await page.getByRole("button", { name: /mark as read/i }).click();

    await expect(page).toHaveURL(
      new RegExp(`/books/${BOOK_ID}/read/3$`)
    );
    // Sidebar: chapter 2 row becomes read (check icon, data-state='read'),
    // chapter 3 row becomes current (data-state='current')
    await expect(
      page
        .getByRole("button", { name: /02 the last of the spirits/i })
    ).toHaveAttribute("data-state", "read");
    await expect(
      page.getByRole("button", { name: /03 chapter 3/i })
    ).toHaveAttribute("data-state", "current");
  });
});
