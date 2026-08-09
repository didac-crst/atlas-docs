import { expect, test } from "@playwright/test";

/**
 * UX pass coverage for the document viewer modal and overflow trash flow.
 * Run: npx playwright test e2e/document-viewer-ux.spec.ts --project=desktop
 */
test("viewer open/close, escape, overflow trash, and no token leak", async ({ page }) => {
  const password = "correct-horse";

  await page.goto("./connect");
  await page.getByLabel(/^Username$/i).fill("ada");
  await page.getByLabel(/^Password$/i).fill(password);
  await page.getByRole("button", { name: /^Sign in$/i }).click();
  await expect(page.getByRole("heading", { name: /^AtlasDocs$/i })).toBeVisible({
    timeout: 15_000,
  });

  await page.getByRole("navigation", { name: /Primary/i }).getByRole("link", { name: /^Explore$/i }).click();
  await expect(page.getByRole("heading", { name: /^Explore$/i })).toBeVisible({
    timeout: 15_000,
  });

  const payslipCard = page.locator(".doc-card").filter({ hasText: /Payslip Germany/i });
  await expect(payslipCard).toBeVisible({ timeout: 15_000 });
  await payslipCard.getByRole("button", { name: /^Document details$/i }).click();
  await expect(page.getByRole("dialog")).toBeVisible({ timeout: 15_000 });
  await expect(page).toHaveURL(/preview=184/);
  await expect(page.getByText(password)).toHaveCount(0);
  await expect(page.getByText(/e2e-exchanged-token/i)).toHaveCount(0);

  await page.keyboard.press("Escape");
  await expect(page.getByRole("dialog")).toHaveCount(0);
  await expect(page).not.toHaveURL(/preview=/);

  await payslipCard.getByRole("button", { name: /^Document details$/i }).click();
  await expect(page.getByRole("dialog")).toBeVisible();
  await page.goBack();
  await expect(page.getByRole("dialog")).toHaveCount(0);

  await page.goto("./documents/184");
  await expect(page).toHaveURL(/\/classify\?.*preview=184/);
  const dialog = page.getByRole("dialog");
  await expect(dialog).toBeVisible();
  await expect(dialog.locator("iframe.document-viewer-frame")).toHaveAttribute(
    "src",
    /\/ui\/api\/documents\/184\/preview$/,
  );
  const technical = dialog.locator(".tech-details").filter({ hasText: /Technical details/i });
  await technical.getByText(/Technical details/i).click();
  await expect(technical).toContainText("184");

  await dialog.getByRole("button", { name: /More actions/i }).click();
  await expect(page.getByRole("menuitem", { name: /Open in Paperless/i })).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(page.getByRole("menuitem", { name: /Open in Paperless/i })).toHaveCount(0);
  await expect(dialog).toBeVisible();

  await dialog.getByRole("button", { name: /^Move to trash$/i }).click();
  await expect(page.getByRole("alertdialog")).toBeVisible();
  await page.getByRole("button", { name: /^Cancel$/i }).click();
  await expect(page.getByRole("alertdialog")).toHaveCount(0);
  await expect(page.getByText(password)).toHaveCount(0);
});

test("mobile full-screen viewer uses dialog chrome", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("./connect");
  await page.getByLabel(/^Username$/i).fill("ada");
  await page.getByLabel(/^Password$/i).fill("correct-horse");
  await page.getByRole("button", { name: /^Sign in$/i }).click();
  await expect(page.getByRole("heading", { name: /^AtlasDocs$/i })).toBeVisible({
    timeout: 15_000,
  });
  await page.getByRole("navigation", { name: /Primary/i }).getByRole("link", { name: /^Explore$/i }).click();
  await expect(page.getByRole("heading", { name: /^Explore$/i })).toBeVisible({
    timeout: 15_000,
  });
  await page.getByRole("button", { name: /^Document details$/i }).first().click();
  const dialog = page.getByRole("dialog");
  await expect(dialog).toBeVisible({ timeout: 15_000 });
  await expect(dialog).toHaveClass(/dialog-panel-mobile-full/);
});
