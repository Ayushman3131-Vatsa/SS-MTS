import { expect, test } from "@playwright/test";

import {
  installSessionApiMock,
  platformPrincipal,
} from "./support/session-api-mock";

const DASHBOARD_TIMEOUT = 45_000;

test.describe("platform dashboard", () => {
  test.describe.configure({ timeout: 60_000 });
  test("renders live platform metrics, activity, and the exact navigation modules", async ({
    page,
  }) => {
    await installSessionApiMock(page, {
      initialPrincipal: platformPrincipal(),
    });

    await page.goto("/platform");

    await expect(page.getByRole("heading", { name: "Dashboard" })).toBeVisible({
      timeout: DASHBOARD_TIMEOUT,
    });
    const totalTenants = page
      .locator("article")
      .filter({ hasText: "Total Tenants" })
      .first();
    await expect(totalTenants.getByText("18", { exact: true })).toBeVisible();
    await expect(
      page
        .locator("article")
        .filter({ hasText: "System Health" })
        .getByText("Healthy", { exact: true }),
    ).toBeVisible();
    await expect(page.getByText("Northstar Labs created")).toBeVisible();

    const navigation = page.getByRole("navigation", {
      name: "Platform navigation",
    });
    await expect(navigation.getByRole("link")).toHaveCount(5);
    await expect(
      navigation.getByRole("link", { name: "Dashboard" }),
    ).toHaveAttribute("aria-current", "page");
    await expect(
      navigation.getByRole("link", { name: "All Tenants" }),
    ).toBeVisible();
    await expect(
      navigation.getByRole("link", { name: "Register Tenant" }),
    ).toBeVisible();
    await expect(
      navigation.getByRole("link", { name: "Offerings" }),
    ).toBeVisible();
    await expect(
      navigation.getByRole("link", { name: "Default Templates" }),
    ).toBeVisible();

    await navigation.getByRole("link", { name: "All Tenants" }).click();
    await expect(
      page.getByRole("heading", { name: "All Tenants" }),
    ).toBeVisible();
    await navigation.getByRole("link", { name: "Register Tenant" }).click();
    await expect(
      page.getByRole("heading", { name: "Register Tenant" }),
    ).toBeVisible();
  });

  test("refetches with validated presets and supports manual refresh", async ({
    page,
  }) => {
    const api = await installSessionApiMock(page, {
      initialPrincipal: platformPrincipal(),
    });
    await page.goto("/platform");
    await expect(page.getByRole("heading", { name: "Dashboard" })).toBeVisible({
      timeout: DASHBOARD_TIMEOUT,
    });
    await expect
      .poll(
        () =>
          api.calls.filter((call) => call.path === "/api/platform/dashboard")
            .length,
      )
      .toBeGreaterThan(0);

    await page
      .getByRole("combobox", { name: "Tenant growth period" })
      .selectOption("6");
    await page
      .getByRole("combobox", { name: "New registration period" })
      .selectOption("7");

    await expect
      .poll(() =>
        api.calls.some(
          (call) =>
            call.path === "/api/platform/dashboard" &&
            call.search?.includes("growth_months=6") &&
            call.search.includes("registration_days=7"),
        ),
      )
      .toBe(true);

    const requestsBeforeRefresh = api.calls.filter(
      (call) => call.path === "/api/platform/dashboard",
    ).length;
    await page.getByRole("button", { name: "Refresh" }).click();
    await expect
      .poll(
        () =>
          api.calls.filter((call) => call.path === "/api/platform/dashboard")
            .length,
      )
      .toBeGreaterThan(requestsBeforeRefresh);
  });

  test("traps focus in the mobile drawer and restores the page on Escape", async ({
    page,
  }) => {
    await page.setViewportSize({ height: 844, width: 390 });
    await installSessionApiMock(page, {
      initialPrincipal: platformPrincipal(),
    });
    await page.goto("/platform");
    await expect(page.getByRole("heading", { name: "Dashboard" })).toBeVisible({
      timeout: DASHBOARD_TIMEOUT,
    });

    const menu = page.locator(
      "button[aria-label='Open platform navigation']",
    );
    await menu.click();

    await expect(menu).toHaveAttribute("aria-expanded", "true");
    const dialog = page.getByRole("dialog", { name: "Platform navigation" });
    await expect(dialog).toHaveAttribute("aria-modal", "true");
    await expect(page.locator("main")).toHaveAttribute("inert", "");
    const close = dialog
      .getByRole("button", {
        name: "Close platform navigation",
        exact: true,
      });
    await expect(close).toBeFocused();
    await expect
      .poll(() => page.evaluate(() => document.body.style.overflow))
      .toBe("hidden");

    const lastNavigationLink = dialog.getByRole("link", {
      name: "Default Templates",
    });
    await lastNavigationLink.focus();
    await page.keyboard.press("Tab");
    await expect(close).toBeFocused();

    await page.keyboard.press("Escape");
    await expect(menu).toHaveAttribute("aria-expanded", "false");
    await expect(menu).toBeFocused();
    await expect
      .poll(() => page.evaluate(() => document.body.style.overflow))
      .toBe("");

    await menu.click();
    await expect
      .poll(() => page.evaluate(() => document.body.style.overflow))
      .toBe("hidden");
    await page.setViewportSize({ height: 844, width: 900 });
    await expect(menu).toHaveAttribute("aria-expanded", "false");
    await expect
      .poll(() => page.evaluate(() => document.body.style.overflow))
      .toBe("");
    await expect(page.getByRole("main")).not.toHaveAttribute("inert");
  });
});
