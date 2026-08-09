import { expect, test } from "@playwright/test";

/**
 * Focused embedded-preview probe: same-origin AtlasDocs BFF, PDF headers,
 * session gate, and no Paperless token leakage. Run alone with:
 *   npx playwright test e2e/embedded-preview.spec.ts --project=desktop
 */
test("embedded preview uses same-origin BFF PDF without leaking tokens", async ({
  page,
}) => {
  const password = "correct-horse";
  const username = "ada";

  await page.goto("./connect");
  await page.getByLabel(/^Username$/i).fill(username);
  await page.getByLabel(/^Password$/i).fill(password);
  await page.getByRole("button", { name: /^Sign in$/i }).click();
  await expect(page.getByRole("heading", { name: /^AtlasDocs$/i })).toBeVisible({
    timeout: 15_000,
  });

  await page.goto("./documents/184");
  const detail = page.locator(".detail-panel");
  await expect(detail.getByRole("heading", { name: /Payslip Germany/i })).toBeVisible();

  const previewFrame = detail.locator("iframe.doc-preview-frame");
  await expect(previewFrame).toHaveAttribute("src", /\/ui\/api\/documents\/184\/preview$/);
  await expect(previewFrame).not.toHaveAttribute("sandbox");
  const previewSrc = await previewFrame.getAttribute("src");
  expect(previewSrc).toBeTruthy();
  expect(previewSrc!).toMatch(/^\/ui\/api\/documents\/184\/preview$/);
  expect(previewSrc!).not.toMatch(/paperless/i);

  await expect(detail.getByRole("link", { name: /^Download$/i })).toHaveAttribute(
    "href",
    /\/ui\/api\/documents\/184\/download$/,
  );
  await expect(
    detail.getByRole("link", { name: /Open original in Paperless/i }),
  ).toHaveAttribute("href", /\/documents\/184\/$/);

  const previewResponse = await page.request.get("/ui/api/documents/184/preview");
  expect(previewResponse.status()).toBe(200);
  expect(previewResponse.headers()["content-type"] ?? "").toMatch(/^application\/pdf\b/);
  expect(previewResponse.headers()["content-disposition"] ?? "").toMatch(/^inline\b/);
  expect(previewResponse.headers()["cache-control"]).toBe("no-store");
  const pdfBytes = await previewResponse.body();
  expect(pdfBytes.subarray(0, 4).toString("latin1")).toBe("%PDF");

  const html = await page.content();
  expect(html).not.toMatch(/e2e-exchanged-token|correct-horse|Token /i);
  expect(html).not.toContain("paperless_token");
  for (const [name, value] of Object.entries(previewResponse.headers())) {
    expect(`${name}:${value}`).not.toMatch(/e2e-exchanged-token|Token /i);
  }

  const downloadResponse = await page.request.get("/ui/api/documents/184/download");
  expect(downloadResponse.status()).toBe(200);
  expect(downloadResponse.headers()["content-disposition"] ?? "").toMatch(/^attachment\b/);

  await page.getByRole("button", { name: /^ada$/i }).click();
  await page.getByRole("menuitem", { name: /Disconnect/i }).click();
  await expect(page.getByRole("heading", { name: /^AtlasDocs$/i })).toBeVisible();
  await expect(page.getByLabel(/^Username$/i)).toBeVisible({ timeout: 15_000 });

  const blocked = await page.request.get("/ui/api/documents/184/preview");
  expect(blocked.status()).toBe(401);
  expect(await blocked.text()).not.toMatch(/e2e-exchanged-token|Token /i);
});
