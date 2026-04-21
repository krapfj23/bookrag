import { test, expect } from "@playwright/test";
import type { Route } from "@playwright/test";

const BOOK_ID = "a_christmas_carol_a1b2c3d4";

const STAGE_KEYS = [
  "parse_epub",
  "run_booknlp",
  "resolve_coref",
  "discover_ontology",
  "review_ontology",
  "run_cognee_batches",
  "validate",
] as const;

function pendingStages() {
  return Object.fromEntries(STAGE_KEYS.map((k) => [k, { status: "pending" }]));
}

async function mockBooksEmpty(page: import("@playwright/test").Page) {
  await page.route("http://localhost:8000/books", async (route: Route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify([]),
    });
  });
}

async function mockUploadSuccess(page: import("@playwright/test").Page) {
  await page.route("http://localhost:8000/books/upload", async (route: Route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ book_id: BOOK_ID, message: "Pipeline started" }),
    });
  });
}

async function mockUpload400(page: import("@playwright/test").Page) {
  await page.route("http://localhost:8000/books/upload", async (route: Route) => {
    await route.fulfill({
      status: 400,
      contentType: "application/json",
      body: JSON.stringify({ detail: "Only .epub files are accepted" }),
    });
  });
}

async function mockStatusRunning(page: import("@playwright/test").Page) {
  await page.route(
    `http://localhost:8000/books/${BOOK_ID}/status`,
    async (route: Route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          book_id: BOOK_ID,
          status: "processing",
          stages: {
            ...pendingStages(),
            parse_epub: { status: "complete", duration_seconds: 0.4 },
            run_booknlp: { status: "running" },
          },
          current_batch: null,
          total_batches: null,
          ready_for_query: false,
        }),
      });
    }
  );
}

test.describe("upload flow (hermetic)", () => {
  test("navigates from Library → Upload → Library without reloading", async ({ page }) => {
    await mockBooksEmpty(page);
    await page.goto("/");
    await expect(page.getByText(/your shelf/i)).toBeVisible();

    await page.getByRole("link", { name: "Upload" }).click();
    await expect(page).toHaveURL(/\/upload$/);
    await expect(page.getByRole("heading", { name: /upload an epub\./i })).toBeVisible();

    await page.getByRole("link", { name: "Library" }).click();
    await expect(page).toHaveURL(/\/$/);
    await expect(page.getByText(/your shelf/i)).toBeVisible();
  });

  test("Upload screen renders the idle Dropzone", async ({ page }) => {
    await mockBooksEmpty(page);
    await page.goto("/upload");
    await expect(page.getByRole("heading", { name: /upload an epub\./i })).toBeVisible();
    await expect(page.getByText(/drop your epub/i)).toBeVisible();
    await expect(page.getByText(/browse files/i)).toBeVisible();
  });

  test("rejecting a non-epub shows the 400 error in the Dropzone", async ({ page }) => {
    await mockBooksEmpty(page);
    await mockUpload400(page);
    await page.goto("/upload");

    // Provide a file via the hidden input (bypassing the native drag)
    await page.setInputFiles('[data-testid="dropzone-input"]', {
      name: "notes.txt",
      mimeType: "text/plain",
      buffer: Buffer.from("hello"),
    });

    const alert = page.getByRole("alert");
    await expect(alert).toContainText(/only \.epub files are accepted/i);
  });

  test("a successful upload renders the 7 pipeline stages", async ({ page }) => {
    await mockBooksEmpty(page);
    await mockUploadSuccess(page);
    await mockStatusRunning(page);
    await page.goto("/upload");

    await page.setInputFiles('[data-testid="dropzone-input"]', {
      name: "a-christmas-carol.epub",
      mimeType: "application/epub+zip",
      buffer: Buffer.from([0x50, 0x4b, 0x03, 0x04]),
    });

    await expect(page.getByText(BOOK_ID)).toBeVisible();
    await expect(page.getByText("Parse EPUB")).toBeVisible();
    await expect(page.getByText("Run BookNLP")).toBeVisible();
    await expect(page.getByText("Resolve coref")).toBeVisible();
    await expect(page.getByText("Discover ontology")).toBeVisible();
    await expect(page.getByText("Review ontology")).toBeVisible();
    await expect(page.getByText("Cognee batches")).toBeVisible();
    await expect(page.getByText("Validate")).toBeVisible();
  });
});
