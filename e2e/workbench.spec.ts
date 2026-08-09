import { expect, test } from "@playwright/test";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));

test("password login, home, ingest, classify without leaking secrets", async ({ page }) => {
  const password = "correct-horse";
  const username = "ada";

  await page.goto("./connect");
  await expect(page.getByRole("heading", { name: /Connect to Paperless/i })).toBeVisible();
  await page.getByLabel(/^Username$/i).fill(username);
  await page.getByLabel(/^Password$/i).fill(password);
  await page.getByRole("button", { name: /^Sign in$/i }).click();

  await expect(page.getByRole("heading", { name: /^AtlasDocs$/i })).toBeVisible({
    timeout: 15000,
  });
  await expect(page.getByText(/Work areas|Needs classification/i).first()).toBeVisible();
  await expect(page.getByText(password)).toHaveCount(0);
  await expect(page.getByText(/e2e-exchanged-token/i)).toHaveCount(0);

  const storageDump = await page.evaluate(() => {
    const dump = (store: Storage) => {
      const entries: Record<string, string> = {};
      for (let i = 0; i < store.length; i += 1) {
        const key = store.key(i);
        if (key) entries[key] = store.getItem(key) || "";
      }
      return entries;
    };
    return { local: dump(window.localStorage), session: dump(window.sessionStorage) };
  });
  expect(JSON.stringify(storageDump)).not.toContain(password);
  expect(JSON.stringify(storageDump).toLowerCase()).not.toContain("token ");

  await page.getByRole("link", { name: /^Ingest$/i }).first().click();
  await expect(page.getByRole("heading", { name: /Ingest document/i })).toBeVisible();
  const sample = path.join(__dirname, "fixtures", "sample.pdf");
  await page.locator('input[type="file"]').setInputFiles(sample);
  await page.getByRole("button", { name: /Upload/i }).click();
  await expect(page.getByText(/READY|PROCESSING|UPLOADING/i).first()).toBeVisible({
    timeout: 20000,
  });
  await expect(page.getByText(password)).toHaveCount(0);

  await page.getByRole("link", { name: /^Explore$/i }).first().click();
  await expect(page.getByRole("heading", { name: /^Explore$/i })).toBeVisible();
  await expect(page.getByRole("tab", { name: /^Documents$/i })).toHaveAttribute(
    "aria-selected",
    "true",
  );
  await page.getByRole("button", { name: /^Grid$/i }).click();
  await expect(page.getByRole("button", { name: /^Grid$/i })).toHaveAttribute(
    "aria-pressed",
    "true",
  );
  await page.getByRole("tab", { name: /^People$/i }).click();
  await expect(page.getByRole("tab", { name: /^People$/i })).toHaveAttribute(
    "aria-selected",
    "true",
  );
  await page.getByLabel(/^Search$/i).fill("Ali");
  await page.getByRole("button", { name: /Apply filters/i }).click();
  const alice = page.getByRole("link", { name: /^Alice$/i });
  await expect(alice.or(page.getByText(/No results for this Explore query/i))).toBeVisible({
    timeout: 15000,
  });
  if (await alice.count()) {
    await alice.first().click();
    await expect(page.getByRole("heading", { name: /^Alice$/i })).toBeVisible();
    await expect(page.getByText(/Related documents|Backlinks|Outgoing relationships/i).first()).toBeVisible();
  }
  await expect(page.getByText(password)).toHaveCount(0);

  await page.getByRole("link", { name: /^Classify$/i }).first().click();
  await expect(page.getByRole("heading", { name: /Needs classification|Classify|Documents/i })).toBeVisible();

  // Select two docs when checkboxes are present
  const checkboxes = page.locator('input[type="checkbox"]');
  const count = await checkboxes.count();
  if (count >= 2) {
    await checkboxes.nth(0).check();
    await checkboxes.nth(1).check();
    await page.getByLabel(/Relationship type/i).first().selectOption("source-country");
    const concept = page.getByLabel(/^Concept$/i).first();
    if (await concept.count()) {
      await concept.fill("Ger");
      const option = page.getByRole("option", { name: /Germany/i });
      if (await option.count()) {
        await option.first().click();
        await page.getByRole("button", { name: /Assign|Apply|Save/i }).first().click();
      }
    }
  }

  await page.goto("./documents/184");
  const detail = page.locator(".detail-panel");
  await expect(detail.getByRole("heading", { name: /Payslip Germany/i })).toBeVisible();

  const previewFrame = detail.locator("iframe.doc-preview-frame");
  await expect(previewFrame).toHaveAttribute("src", /\/ui\/api\/documents\/184\/preview$/);
  const openPreview = detail.getByRole("link", { name: /Open preview in new tab/i });
  await expect(openPreview).toHaveAttribute("href", /\/ui\/api\/documents\/184\/preview$/);
  const download = detail.getByRole("link", { name: /^Download$/i });
  await expect(download).toHaveAttribute("href", /\/ui\/api\/documents\/184\/download$/);
  const paperless = detail.getByRole("link", { name: /Open original in Paperless/i });
  await expect(paperless).toHaveAttribute(
    "href",
    "http://paperless.example.test/documents/184/",
  );
  await expect(paperless).toHaveAttribute("target", "_blank");

  await page.getByRole("link", { name: /Reconcile/i }).first().click();
  await expect(page.getByRole("heading", { name: /reconciliation/i })).toBeVisible();
  await page.getByRole("button", { name: /Run reconciliation/i }).click();
  await expect(page.getByText(/Dry-run complete/i)).toBeVisible();
  await expect(page.getByText(password)).toHaveCount(0);
});

test("advanced token connect still works without leaking token", async ({ page }) => {
  const secret = "e2e-paperless-token-should-never-leak";
  await page.goto("./connect");
  await page.getByText(/Advanced: paste API token/i).click();
  await page.getByLabel(/Paperless token/i).fill(secret);
  await page.getByRole("button", { name: /Connect with token/i }).click();
  await expect(page.getByRole("heading", { name: /^AtlasDocs$/i })).toBeVisible();
  await expect(page.getByText(secret)).toHaveCount(0);
});
