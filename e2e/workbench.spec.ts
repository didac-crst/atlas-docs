import { expect, test } from "@playwright/test";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));

test("password login, home, ingest, classify without leaking secrets", async ({ page }) => {
  const password = "correct-horse";
  const username = "ada";

  await page.goto("./connect");
  await expect(page.getByRole("heading", { name: /^AtlasDocs$/i })).toBeVisible();
  await expect(page.getByText(/Where evidence becomes knowledge/i).first()).toBeVisible();
  await expect(page.getByText(/Secure authentication powered by Paperless/i)).toBeVisible();
  await page.getByLabel(/^Username$/i).fill(username);
  await page.getByLabel(/^Password$/i).fill(password);
  await page.getByRole("button", { name: /^Sign in$/i }).click();

  await expect(page.getByRole("heading", { name: /^AtlasDocs$/i })).toBeVisible({
    timeout: 15000,
  });
  await expect(page.getByText(/Where evidence becomes knowledge/i).first()).toBeVisible();
  await expect(page.getByRole("heading", { name: /^Work areas$/i })).toBeVisible({
    timeout: 15000,
  });
  await expect(page.getByText(/Needs classification/i).first()).toBeVisible();
  await expect(page.getByText(/Powered by Paperless-ngx/i)).toBeVisible();
  const primaryNav = page.getByRole("navigation", { name: /Primary/i });
  await expect(primaryNav.getByRole("link", { name: /^Home$/i })).toBeVisible();
  await expect(primaryNav.getByRole("link", { name: /^Explore$/i })).toBeVisible();
  await expect(primaryNav.getByRole("link", { name: /^Classify$/i })).toBeVisible();
  await expect(primaryNav.getByRole("link", { name: /^Ingest$/i })).toBeVisible();
  await expect(primaryNav.getByRole("link", { name: /Reconcile/i })).toHaveCount(0);
  await expect(primaryNav.getByRole("button", { name: /Disconnect/i })).toHaveCount(0);
  await expect(page.getByRole("search")).toBeVisible();
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
  await expect(page.getByRole("button", { name: /^Grid$/i })).toHaveAttribute(
    "aria-pressed",
    "true",
  );
  await page.getByRole("button", { name: /^List$/i }).click();
  await expect(page.getByRole("button", { name: /^List$/i })).toHaveAttribute(
    "aria-pressed",
    "true",
  );
  await page.getByRole("button", { name: /^Grid$/i }).click();
  await expect(page.getByRole("button", { name: /^Grid$/i })).toHaveAttribute(
    "aria-pressed",
    "true",
  );
  await page.getByRole("tab", { name: /^Knowledge$/i }).click();
  await expect(page.getByRole("tab", { name: /^Knowledge$/i })).toHaveAttribute(
    "aria-selected",
    "true",
  );
  await page.getByRole("tab", { name: /^People$/i }).click();
  await expect(page.getByRole("tab", { name: /^People$/i })).toHaveAttribute(
    "aria-selected",
    "true",
  );
  await page.getByLabel(/^Search$/i).fill("Ali");
  await page.getByRole("button", { name: /^Apply$/i }).click();
  const alice = page.getByRole("link", { name: /^Alice$/i });
  await expect(alice.or(page.getByText(/No results for this Explore query/i))).toBeVisible({
    timeout: 15000,
  });
  if (await alice.count()) {
    await alice.first().click();
    await expect(page.getByRole("heading", { name: /^Alice$/i })).toBeVisible();
    await expect(page.getByText(/Related documents|Backlinks|Outgoing relationships/i).first()).toBeVisible();
    await expect(page.getByText(/Master Data/i).first()).toBeVisible();
  }
  await expect(page.getByText(password)).toHaveCount(0);

  await page.getByRole("link", { name: /^About$/i }).first().click();
  await expect(page.getByRole("heading", { name: /^AtlasDocs$/i })).toBeVisible();
  await expect(page.getByText(/Where evidence becomes knowledge/i).first()).toBeVisible();
  await expect(page.getByText(/transforms document archives into connected knowledge/i)).toBeVisible();
  await expect(page.getByText(password)).toHaveCount(0);

  await page.getByRole("link", { name: /^Classify$/i }).first().click();
  await expect(page.getByRole("heading", { name: /^Classify$/i })).toBeVisible();
  // Shared e2e server may retain prior classification; open Filters and use Any.
  await page.getByRole("button", { name: /Filters/i }).click();
  await page.getByLabel(/^Classification$/i).selectOption("any");
  await page.getByRole("button", { name: /^Apply$/i }).click();
  await expect(page.getByText(/No unclassified documents|No documents|shown/i).first()).toBeVisible();

  await page.getByRole("button", { name: /Select visible/i }).click();
  await expect(page.getByRole("region", { name: /Batch actions/i })).toBeVisible();
  await page.getByRole("button", { name: /Add relationship/i }).click();
  await expect(page.getByRole("dialog")).toBeVisible();
  // Bulk assign offers Concept/Document targets; document-type is valid for Concept.
  await page.getByLabel(/Target entity type/i).first().selectOption("concept");
  await page.getByLabel(/Relationship type/i).first().selectOption("document-type");
  const target = page.getByLabel(/^Target$/i).first();
  await expect(target).toBeVisible();
  await target.fill("Inv");
  const option = page.getByRole("option", { name: /Invoice/i });
  await expect(option.first()).toBeVisible({ timeout: 10000 });
  await option.first().click();
  await page.getByRole("button", { name: /Assign to selected/i }).first().click();

  await page.goto("./documents/184");
  await expect(page).toHaveURL(/\/classify\?.*preview=184/);
  const dialog = page.getByRole("dialog");
  await expect(dialog).toBeVisible();
  await expect(dialog.getByRole("heading", { name: /Payslip Germany|Document preview/i }).first()).toBeVisible();
  await expect(dialog.locator("iframe.document-viewer-frame")).toHaveAttribute(
    "src",
    /\/ui\/api\/documents\/184\/preview$/,
  );
  await expect(dialog.getByRole("button", { name: /^Move to trash$/i })).toBeVisible();
  await dialog.getByRole("button", { name: /More actions/i }).click();
  const paperless = page.getByRole("menuitem", { name: /Open in Paperless/i });
  await expect(paperless).toHaveAttribute(
    "href",
    "http://paperless.example.test/documents/184/",
  );
  await expect(paperless).toHaveAttribute("target", "_blank");
  await page.keyboard.press("Escape");
  await expect(page.getByRole("menuitem", { name: /Open in Paperless/i })).toHaveCount(0);

  await dialog.getByRole("button", { name: /^Move to trash$/i }).click();
  await expect(page.getByRole("alertdialog")).toBeVisible();
  await expect(page.getByText(/Move this document to trash/i)).toBeVisible();
  await page.getByRole("button", { name: /^Cancel$/i }).click();
  await expect(page.getByRole("alertdialog")).toHaveCount(0);
  await expect(dialog.getByRole("button", { name: /^Move to trash$/i })).toBeVisible();
  await expect(page.getByText(password)).toHaveCount(0);

  await dialog.getByRole("button", { name: /^Close$/i }).click();
  await expect(page.getByRole("dialog")).toHaveCount(0);

  await page.getByRole("button", { name: /^ada$/i }).click();
  await page.getByRole("menuitem", { name: /Reconcile/i }).click();
  await expect(page.getByRole("heading", { name: /reconciliation/i })).toBeVisible();
  await page.getByRole("button", { name: /Run reconciliation/i }).click();
  await expect(page.getByText(/Dry-run complete/i)).toBeVisible();
  await expect(page.getByText(password)).toHaveCount(0);
});

test("advanced token connect still works without leaking token", async ({ page }) => {
  const secret = "e2e-paperless-token-should-never-leak";
  await page.goto("./connect");
  await page.getByText(/Advanced: paste API token/i).click();
  await page.getByLabel(/API token/i).fill(secret);
  await page.getByRole("button", { name: /Connect with token/i }).click();
  await expect(page.getByRole("heading", { name: /^AtlasDocs$/i })).toBeVisible();
  await expect(page.getByText(secret)).toHaveCount(0);
});
