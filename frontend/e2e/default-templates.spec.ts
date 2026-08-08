import { expect, test } from "@playwright/test";

import {
  CREATED_TEMPLATE_ID,
  DEFAULT_TEMPLATE_E2E_IDS,
  installDefaultTemplatesApiMock,
} from "./support/default-templates-api-mock";
import {
  installSessionApiMock,
  platformPrincipal,
} from "./support/session-api-mock";

const PAGE_TIMEOUT = 45_000;

test.describe("platform default templates", () => {
  test.describe.configure({ timeout: 60_000 });
  test("selects a catalog context and creates a published default from the full-page editor", async ({
    page,
  }) => {
    await installSessionApiMock(page, {
      initialPrincipal: platformPrincipal(),
    });
    const api = await installDefaultTemplatesApiMock(page);

    await page.goto("/platform/default-templates");

    await expect(
      page.getByRole("heading", { name: "Default templates", exact: true }),
    ).toBeVisible({ timeout: PAGE_TIMEOUT });
    await expect(page).toHaveURL(
      new RegExp(`offering_id=${DEFAULT_TEMPLATE_E2E_IDS.coreHrOffering}`),
    );
    await expect(page.getByText("Employee welcome", { exact: true })).toBeVisible();
    await expect(page.getByText("11", { exact: true }).first()).toBeVisible();

    await page.getByRole("button", { name: "Letter", exact: true }).click();
    await expect(page).toHaveURL(/type=LETTER/);
    await expect(
      page.getByRole("heading", { name: "No templates match these filters" }),
    ).toBeVisible();

    await page.getByRole("link", { name: "New default template" }).click();
    await expect(page).toHaveURL(
      new RegExp(`/platform/default-templates/new\\?.*offering_id=${DEFAULT_TEMPLATE_E2E_IDS.coreHrOffering}.*type=LETTER`),
    );
    await expect(
      page.getByRole("heading", { name: "Create default template" }),
    ).toBeVisible({ timeout: PAGE_TIMEOUT });
    await expect(page.getByRole("combobox", { name: "Offering" })).toHaveValue(
      DEFAULT_TEMPLATE_E2E_IDS.coreHrOffering,
    );
    await expect(page.getByRole("combobox", { name: "Template type" })).toHaveValue("LETTER");

    await page.getByRole("textbox", { name: "Display name" }).fill("Employment verification");
    await expect(page.getByRole("textbox", { name: "Template code" })).toHaveValue(
      "corehr_employment_verification",
    );
    await page.getByLabel("Description").fill("Confirms current employment for an external recipient.");
    await page.getByLabel("Display order").fill("25");
    await page.getByLabel(/Subject/).fill("Employment confirmation");
    await page.getByLabel(/Template body/).fill("This letter confirms the employment of ");

    await page.getByRole("button", { name: "Add placeholder" }).click();
    await page.getByRole("textbox", { name: "Key" }).fill("employee_name");
    await page.getByLabel("Label").fill("Employee name");
    await page.getByLabel("Sample value").fill("Ada Lovelace");
    await page.getByRole("checkbox", { name: "Required value" }).check();
    await page
      .getByRole("button", { name: "Insert {{employee_name}}" })
      .click();
    await expect(page.getByLabel(/Template body/)).toHaveValue(
      "This letter confirms the employment of {{employee_name}}",
    );

    await page.getByRole("button", { name: "Preview draft" }).first().click();
    const preview = page.getByRole("dialog", {
      name: /Live Preview.*Employment verification/,
    });
    await expect(preview).toBeVisible();
    await expect(preview).toContainText("Employment confirmation");
    await expect(preview).toContainText("This letter confirms the employment of Ada Lovelace");
    await preview.getByRole("button", { name: "Done" }).click();

    await page.getByRole("button", { name: "Create & publish" }).first().click();

    await expect(page).toHaveURL(new RegExp(`/platform/default-templates/${CREATED_TEMPLATE_ID}`));
    await expect(
      page.getByRole("heading", { name: "Employment verification" }),
    ).toBeVisible({ timeout: PAGE_TIMEOUT });
    await expect(page.getByText("Published", { exact: true })).toBeVisible();
    await expect(page.getByRole("textbox", { name: "Template code" })).toBeDisabled();

    const createCall = api.calls.find(
      (call) => call.method === "POST" && call.path === "/api/platform/default-templates",
    );
    expect(createCall?.payload).toMatchObject({
      offering_id: DEFAULT_TEMPLATE_E2E_IDS.coreHrOffering,
      type: "LETTER",
      code: "corehr_employment_verification",
      name: "Employment verification",
      subject: "Employment confirmation",
      body: "This letter confirms the employment of {{employee_name}}",
      sort_order: 25,
      placeholders: [
        {
          key: "employee_name",
          label: "Employee name",
          sample_value: "Ada Lovelace",
          required: true,
        },
      ],
    });
  });

  test("uses the mobile navigation and stacks the offering catalog without horizontal overflow", async ({
    page,
  }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await installSessionApiMock(page, {
      initialPrincipal: platformPrincipal(),
    });
    await installDefaultTemplatesApiMock(page);

    await page.goto("/platform");
    await expect(page.getByRole("heading", { name: "Dashboard" })).toBeVisible({
      timeout: PAGE_TIMEOUT,
    });

    const menu = page.getByRole("button", { name: "Open platform navigation" });
    await menu.click();
    const drawer = page.getByRole("dialog", { name: "Platform navigation" });
    await expect(drawer).toBeVisible();
    await drawer.getByRole("link", { name: "Default Templates" }).click();

    await expect(menu).toHaveAttribute("aria-expanded", "false");
    await expect(
      page.getByRole("heading", { name: "Default templates", exact: true }),
    ).toBeVisible({ timeout: PAGE_TIMEOUT });
    await expect(page).toHaveURL(
      new RegExp(`offering_id=${DEFAULT_TEMPLATE_E2E_IDS.coreHrOffering}`),
    );

    await page
      .getByRole("button", { name: /Task Management TASKMGMT Inactive/ })
      .click();
    await expect(page).toHaveURL(
      new RegExp(`offering_id=${DEFAULT_TEMPLATE_E2E_IDS.taskManagementOffering}`),
    );
    await expect(page.getByText("Inactive offering", { exact: true })).toBeVisible();
    await page.getByRole("button", { name: "Notification", exact: true }).click();
    await expect(page.getByText("Assignment due", { exact: true })).toBeVisible();

    const offeringPanel = page.locator("aside[aria-label='Filter by offering']");
    const catalog = page.locator("aside[aria-label='Filter by offering'] + main");
    const panelBox = await offeringPanel.boundingBox();
    const catalogBox = await catalog.boundingBox();
    expect(panelBox).not.toBeNull();
    expect(catalogBox).not.toBeNull();
    expect(Math.abs((panelBox?.x ?? 0) - (catalogBox?.x ?? 0))).toBeLessThan(2);
    expect(Math.abs((panelBox?.width ?? 0) - (catalogBox?.width ?? 0))).toBeLessThan(2);
    expect(catalogBox?.y ?? 0).toBeGreaterThanOrEqual(
      (panelBox?.y ?? 0) + (panelBox?.height ?? 0) - 1,
    );
    await expect
      .poll(() => page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1))
      .toBe(true);
  });
});
