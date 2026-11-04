import { test, expect, type Page } from "@playwright/test";
import { mkdirSync } from "node:fs";
const password = "e2e-workspace-password-strong-and-local";
const backend = process.env.E2E_TRACKER_API_URL || "http://127.0.0.1:8003";
const headers = { Authorization: "Bearer e2e-admin-" + "a".repeat(40) };
const unique = () => Math.random().toString(36).slice(2, 10);
async function login(page: Page) {
  await page.goto("/login");
  await page.getByLabel("Workspace password", { exact: true }).fill(password);
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(page).toHaveURL(/\/overview$/);
}
test("English default ignores browser language; switching preserves form and route", async ({
  page,
  context,
}) => {
  await context.setExtraHTTPHeaders({ "Accept-Language": "fa-IR,fa;q=0.9" });
  await page.goto("/login");
  await expect(page.locator("html")).toHaveAttribute("lang", "en");
  await page.getByLabel("Workspace password", { exact: true }).fill(password);
  await page.getByRole("button", { name: "FA", exact: true }).click();
  await expect(page.getByLabel("رمز فضای کاری", { exact: true })).toHaveValue(
    password,
  );
  await expect(page.locator("html")).toHaveAttribute("dir", "rtl");
  await page.getByRole("button", { name: "ورود", exact: true }).click();
  await expect(page).toHaveURL(/\/overview$/);
  await page
    .getByRole("navigation")
    .getByRole("link", { name: "کمپین‌ها", exact: true })
    .click();
  await page.getByRole("button", { name: "ساخت کمپین", exact: true }).click();
  await page.getByLabel("نام کمپین", { exact: true }).fill("Draft retained");
  await page.getByRole("button", { name: "EN", exact: true }).click();
  await expect(page.getByLabel("Campaign name", { exact: true })).toHaveValue(
    "Draft retained",
  );
  await expect(page).toHaveURL(/\/campaigns$/);
  await page.getByRole("button", { name: "Cancel", exact: true }).click();
  await page.getByRole("button", { name: "FA", exact: true }).click();
  await page.reload();
  await expect(page.locator("html")).toHaveAttribute("lang", "fa");
  await expect(page.getByRole("navigation").getByRole("link")).toHaveText([
    "نمای کلی",
    "کمپین‌ها",
    "لینک‌ها",
    "مقصدها",
    "تحلیل ترافیک",
    "گزارش کلیک‌ها",
  ]);
});
test("campaign autocomplete is explicit, keyboard accessible, clearable; duplicate names fail", async ({
  page,
}) => {
  await login(page);
  await page
    .getByRole("navigation")
    .getByRole("link", { name: "Campaigns", exact: true })
    .click();
  const name = "Autumn " + unique();
  await page
    .getByRole("button", { name: "Create campaign", exact: true })
    .click();
  await page
    .getByLabel("Campaign name", { exact: true })
    .fill("  " + name + "  ");
  await page.getByRole("button", { name: "Create", exact: true }).click();
  await expect(page.getByRole("cell", { name, exact: true })).toBeVisible();
  await page
    .getByRole("button", { name: "Create campaign", exact: true })
    .click();
  await page
    .getByLabel("Campaign name", { exact: true })
    .fill(" " + name.toUpperCase() + " ");
  await page.getByRole("button", { name: "Create", exact: true }).click();
  await expect(page.getByRole("alert")).toContainText("already exists");
  await page.getByRole("button", { name: "Cancel", exact: true }).click();
  const search = page.getByRole("combobox", {
    name: "Search campaigns",
    exact: true,
  });
  await search.fill("no-match-" + unique());
  await expect(
    page.getByText("No matching campaigns.", { exact: true }),
  ).toBeVisible();
  await expect(page.getByRole("cell", { name, exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Search", exact: true }).click();
  await expect(page.getByRole("cell", { name, exact: true })).toHaveCount(0);
  await page.getByRole("button", { name: "Clear", exact: true }).click();
  await search.fill(name.slice(0, -1).toUpperCase());
  await expect(page.getByRole("option").first()).toBeVisible();
  await search.press("ArrowDown");
  await search.press("Enter");
  await expect(page.getByRole("cell", { name, exact: true })).toBeVisible();
});
test("links, destination versions, redirects, analytics and soft deletion", async ({
  page,
  request,
}) => {
  await login(page);
  await page
    .getByRole("navigation")
    .getByRole("link", { name: "Links", exact: true })
    .click();
  await page
    .getByRole("button", { name: "Create tracking link", exact: true })
    .click();
  const slug = "e2e-" + unique();
  await page
    .getByLabel("Destination URL", { exact: true })
    .fill("https://example.com/?signature=a%2Fb");
  await page.getByLabel("Custom slug (optional)", { exact: true }).fill(slug);
  await page.getByRole("button", { name: "FA", exact: true }).click();
  await expect(page.getByLabel("آدرس مقصد", { exact: true })).toHaveValue(
    "https://example.com/?signature=a%2Fb",
  );
  await page.getByRole("button", { name: "EN", exact: true }).click();
  await page
    .getByRole("dialog")
    .getByRole("button", { name: "Create tracking link", exact: true })
    .click();
  await expect(
    page.getByRole("cell").filter({ hasText: slug }).first(),
  ).toBeVisible();
  await page.context().grantPermissions(["clipboard-read", "clipboard-write"]);
  const createdRow = page.getByRole("row").filter({ hasText: slug });
  await createdRow
    .getByRole("button", { name: "Copy tracking URL", exact: true })
    .click();
  await expect
    .poll(() => page.evaluate(() => navigator.clipboard.readText()))
    .toBe(backend + "/r/" + slug);
  await expect(page.getByRole("dialog")).toHaveCount(0);
  await expect(createdRow.getByRole("status")).toHaveText(
    "Tracking URL copied.",
  );
  const redirect = await request.get(backend + "/r/" + slug, {
    maxRedirects: 0,
  });
  expect(redirect.status()).toBe(302);
  expect(redirect.headers().location).toBe(
    "https://example.com/?signature=a%2Fb",
  );
  await page.getByRole("button", { name: "Edit " + slug, exact: true }).click();
  await page
    .getByLabel("Add destination", { exact: true })
    .fill("https://t.me/testchannel");
  await page
    .getByRole("button", { name: "Add destination", exact: true })
    .click();
  await expect(
    page.getByText("https://t.me/testchannel", { exact: true }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Make active", exact: true }).click();
  await expect(
    page.getByText("Active destination", { exact: true }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Close", exact: true }).click();
  const links = await request.get(backend + "/api/v1/links", {
    headers,
    params: { q: slug },
  });
  const link = (await links.json())[0];
  expect(link.slug).toBe(slug);
  await page
    .getByRole("navigation")
    .getByRole("link", { name: "Traffic Analytics", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: "Traffic Analytics", exact: true }),
  ).toBeVisible();
  await page.getByLabel("Links", { exact: true }).selectOption(link.id);
  await page
    .getByRole("button", { name: "Apply filters", exact: true })
    .click();
  await expect(page.locator("svg.recharts-surface").first()).toBeVisible();
  await page
    .getByRole("navigation")
    .getByRole("link", { name: "Links", exact: true })
    .click();
  await page
    .getByRole("button", { name: "Delete " + slug, exact: true })
    .click();
  await page
    .getByRole("dialog")
    .getByRole("button", { name: "Delete", exact: true })
    .click();
  await expect(page.getByRole("dialog")).toHaveCount(0);
  const deleted = await request.get(backend + "/api/v1/links/" + link.id, {
    headers,
  });
  expect((await deleted.json()).status).toBe("deleted");
});
test("authenticated boundary rejects unauthenticated, cross-origin and arbitrary upstream requests", async ({
  page,
  request,
}) => {
  const payloads: Promise<string>[] = [];
  page.on("response", (response) => {
    const type = response.headers()["content-type"] || "";
    if (/json|javascript|html|text\/x-component/.test(type))
      payloads.push(response.text().catch(() => ""));
  });
  const anonymous = await request.get("/api/tracker/links");
  expect(anonymous.status()).toBe(401);
  await login(page);
  await expect(
    page.getByText("Your marketing, in focus.", { exact: true }),
  ).toBeVisible();
  mkdirSync("../.local", { recursive: true });
  await page.screenshot({
    path: "../.local/nextjs-overview-en.png",
    fullPage: true,
  });
  await page.getByRole("button", { name: "FA", exact: true }).click();
  await page.screenshot({
    path: "../.local/nextjs-overview-fa.png",
    fullPage: true,
  });
  const evil = await page.request.post("/api/tracker/campaigns", {
    headers: { origin: "https://evil.example" },
    data: { name: "Forbidden" },
  });
  expect(evil.status()).toBe(403);
  const route = await page.request.get("/api/tracker/health/ready");
  expect(route.status()).toBe(404);
  const text = await page.content();
  expect(text).not.toContain(headers.Authorization);
  expect(text).not.toContain("e2e-session-secret");
  const responses = (await Promise.all(payloads)).join("\n");
  for (const secret of [
    "e2e-admin-" + "a".repeat(40),
    "e2e-report-" + "b".repeat(40),
    "e2e-session-secret-".repeat(4),
    "postgresql+psycopg://",
  ])
    expect(responses).not.toContain(secret);
});
test("mobile RTL navigation and report filters survive language changes", async ({
  page,
}) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await login(page);
  await page.getByRole("button", { name: "FA", exact: true }).click();
  await page.getByRole("button", { name: "بازکردن منو", exact: true }).click();
  await page
    .getByRole("navigation")
    .getByRole("link", { name: "گزارش کلیک‌ها", exact: true })
    .click();
  await expect(page).toHaveURL(/\/clicks$/);
  const from = page.getByLabel("از تاریخ", { exact: true });
  await from.fill("2026-11-01");
  await page.getByRole("button", { name: "EN", exact: true }).click();
  await expect(page.getByLabel("From", { exact: true })).toHaveValue(
    "2026-11-01",
  );
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth > innerWidth,
    ),
  ).toBe(false);
  await expect(page.locator("html")).toHaveAttribute("dir", "ltr");
  await page.screenshot({
    path: "../.local/nextjs-mobile.png",
    fullPage: true,
  });
});

test("click report cursor pagination is preserved through the authenticated UI", async ({
  page,
  request,
}) => {
  const created = await request.post(backend + "/api/v1/links", {
    headers,
    data: {
      destination_url: "https://example.com/paging",
      slug: "paged-" + unique(),
    },
  });
  expect(created.status()).toBe(201);
  const link = await created.json();
  for (let i = 0; i < 102; i++)
    expect(
      (
        await request.get(backend + "/r/" + link.slug, { maxRedirects: 0 })
      ).status(),
    ).toBe(302);
  await login(page);
  await page
    .getByRole("navigation")
    .getByRole("link", { name: "Click Reports", exact: true })
    .click();
  await page.getByLabel("Links", { exact: true }).selectOption(link.id);
  await page
    .getByRole("button", { name: "Apply filters", exact: true })
    .click();
  await expect(page.locator("tbody tr")).toHaveCount(100);
  await page.getByRole("button", { name: "Next", exact: true }).click();
  await expect(page.locator("tbody tr")).toHaveCount(2);
  await page.getByRole("button", { name: "Previous", exact: true }).click();
  await expect(page.locator("tbody tr")).toHaveCount(100);
});
