import { expect, test } from "@playwright/test";

test("connect, classify, reconcile without leaking token", async ({ page }) => {
  const secret = "e2e-paperless-token-should-never-leak";

  await page.goto("./connect");
  await expect(page.getByRole("heading", { name: /Connect to Paperless/i })).toBeVisible();
  await page.getByLabel(/Paperless token/i).fill(secret);
  await page.getByRole("button", { name: /^Connect$/i }).click();

  await expect(page.getByRole("heading", { name: /Needs classification/i })).toBeVisible();
  await expect(page.getByText(secret)).toHaveCount(0);

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
  expect(JSON.stringify(storageDump)).not.toContain(secret);
  expect(JSON.stringify(storageDump).toLowerCase()).not.toContain("token ");

  // Deep-link so viewport-specific queue hide rules and shared e2e DB state cannot block.
  await page.goto("./documents/184");
  const detail = page.locator(".detail-panel");
  await expect(detail.getByRole("heading", { name: /Payslip Germany/i })).toBeVisible();
  await expect(detail.getByText(/Acme Payroll/)).toBeVisible();
  await expect(detail.getByText(/2024-01-15/)).toBeVisible();

  const existing = detail.getByRole("button", { name: /Remove source-country Germany/i });
  if (await existing.count()) {
    await existing.click();
    await expect(page.getByText(/Relationship removed/i)).toBeVisible();
  }

  await page.getByLabel(/Relationship type/i).selectOption("source-country");
  await page.getByLabel(/^Concept$/i).fill("Ger");
  await page.getByRole("option", { name: /Germany/i }).click();
  await page.getByRole("button", { name: /^Save$/i }).click();
  await expect(page.getByText(/Relationship saved/i)).toBeVisible();
  await expect(page.getByText(/Provenance: manual/i)).toBeVisible();
  await expect(page.getByText(secret)).toHaveCount(0);

  await page.getByRole("link", { name: /Reconcile/i }).click();
  await expect(page.getByRole("heading", { name: /reconciliation/i })).toBeVisible();
  await expect(page.getByText(/never deleted/i)).toBeVisible();
  await page.getByRole("button", { name: /Run reconciliation/i }).click();
  await expect(page.getByText(/Dry-run complete/i)).toBeVisible();
  await expect(page.getByText(secret)).toHaveCount(0);
});
