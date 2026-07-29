import { expect, test } from "@playwright/test";

import {
  installSessionApiMock,
  platformPrincipal,
  tenantPrincipal,
  type SessionPrincipal,
} from "./support/session-api-mock";

const PASSWORD = "ExistingAccountPassword!";

const submitTenantLogin = async (
  page: Parameters<typeof installSessionApiMock>[0],
  rememberWorkspace = false,
) => {
  await page
    .getByRole("textbox", { name: "Workspace", exact: true })
    .fill("northstar-labs");
  await page
    .getByRole("textbox", { name: "Work email", exact: true })
    .fill("Member@Northstar.Example");
  await page.locator("#tenant-password").fill(PASSWORD);
  if (rememberWorkspace) {
    await page
      .getByRole("checkbox", { name: "Remember workspace", exact: true })
      .check();
  }
  await page.getByRole("button", { name: "Sign in to workspace" }).click();
};

const submitPlatformLogin = async (
  page: Parameters<typeof installSessionApiMock>[0],
) => {
  await page
    .getByRole("textbox", { name: "Administrator email", exact: true })
    .fill("Operator@Platform.Example");
  await page.locator("#platform-password").fill(PASSWORD);
  await page
    .getByRole("button", { name: "Sign in to platform console" })
    .click();
};

test.describe("secure multi-tenant login", () => {
  test("redirects unauthenticated protected-route access to tenant login", async ({
    page,
  }) => {
    await installSessionApiMock(page);

    await page.goto("/app/overview");

    await expect(page).toHaveURL(/\/login$/);
    await expect(
      page.getByRole("heading", { name: "Welcome back" }),
    ).toBeVisible();
    await expect(
      page.getByRole("textbox", { name: "Workspace", exact: true }),
    ).toBeVisible();
  });

  test("renders tenant-first login and switches to the restricted platform form", async ({
    page,
  }) => {
    await installSessionApiMock(page);

    await page.goto("/");

    await expect(page).toHaveURL(/\/login$/);
    await expect(
      page.getByRole("textbox", { name: "Workspace", exact: true }),
    ).toBeVisible();
    await expect(
      page.getByRole("textbox", { name: "Work email", exact: true }),
    ).toBeVisible();
    await expect(page.locator("#tenant-password")).toHaveAttribute(
      "autocomplete",
      "current-password",
    );
    await page.getByRole("link", { name: "Platform administrator" }).click();

    await expect(page).toHaveURL(/\/login\/platform$/);
    await expect(
      page.getByRole("heading", { name: "Administrator sign in" }),
    ).toBeVisible();
    await expect(page.getByText("Authorized operators only.")).toBeVisible();
    await expect(
      page.getByRole("textbox", { name: "Workspace", exact: true }),
    ).toHaveCount(0);

    await page
      .getByRole("link", { name: "Back to organization sign in" })
      .click();
    await expect(page).toHaveURL(/\/login$/);
  });

  const roleCases: Array<{
    expectedHeading: RegExp | string;
    expectedPath: string;
    principal: SessionPrincipal;
  }> = [
    {
      principal: platformPrincipal(),
      expectedPath: "/platform",
      expectedHeading: "Dashboard",
    },
    {
      principal: tenantPrincipal("Tenant Admin"),
      expectedPath: "/app/overview",
      expectedHeading: "Your workspace is ready",
    },
    {
      principal: tenantPrincipal("Project Manager"),
      expectedPath: "/app/overview",
      expectedHeading: "Your workspace is ready",
    },
    {
      principal: tenantPrincipal("Employee"),
      expectedPath: "/app/my-work",
      expectedHeading: /securely signed in$/,
    },
  ];

  for (const { expectedHeading, expectedPath, principal } of roleCases) {
    test(`routes ${principal.role} to ${expectedPath}`, async ({ page }) => {
      const api = await installSessionApiMock(page, {
        loginPrincipal: principal,
      });

      if (principal.principal_type === "platform_admin") {
        await page.goto("/login/platform");
        await submitPlatformLogin(page);
      } else {
        await page.goto("/login");
        await submitTenantLogin(page);
      }

      await expect(page).toHaveURL(expectedPath);
      await expect(
        page.getByRole("heading", { name: expectedHeading }),
      ).toBeVisible({
        timeout:
          principal.principal_type === "platform_admin" ? 20_000 : 5_000,
      });
      await expect(page.getByText(principal.role, { exact: true })).toBeVisible();

      const loginCall = api.calls.find((call) => call.method === "POST");
      expect(loginCall?.path).toBe(
        principal.principal_type === "platform_admin"
          ? "/api/auth/session/platform"
          : "/api/auth/session/tenant",
      );
      expect(loginCall?.payload).toEqual(
        principal.principal_type === "platform_admin"
          ? {
              email: "operator@platform.example",
              password: PASSWORD,
            }
          : {
              email: "member@northstar.example",
              password: PASSWORD,
              workspace_slug: "northstar-labs",
            },
      );
      expect(loginCall?.payload).not.toHaveProperty("role");
    });
  }

  test("shows a generic, focused invalid-credentials alert", async ({
    page,
  }) => {
    await installSessionApiMock(page, {
      loginFailure: { status: 401 },
    });
    await page.goto("/login");

    await submitTenantLogin(page);

    const alert = page.getByRole("alert");
    await expect(alert).toContainText("Unable to sign in");
    await expect(alert).toContainText(
      "The workspace or credentials are not recognized.",
    );
    await expect
      .poll(() =>
        page.evaluate(() => document.activeElement?.textContent ?? ""),
      )
      .toContain("Unable to sign in");
  });

  test("surfaces a Retry-After lockout without exposing account state", async ({
    page,
  }) => {
    await installSessionApiMock(page, {
      loginFailure: { status: 429, retryAfterSeconds: 120 },
    });
    await page.goto("/login/platform");

    await submitPlatformLogin(page);

    const alert = page.getByRole("alert");
    await expect(alert).toContainText("Too many sign-in attempts");
    await expect(alert).toContainText("Try again in 2 minutes.");
    await expect(alert).not.toContainText("account");
  });

  test("logs out with the CSRF header and returns to the login screen", async ({
    context,
    page,
  }) => {
    await context.addCookies([
      {
        name: "mt_csrf",
        value: "e2e-csrf-token",
        url: "http://127.0.0.1:5173",
        sameSite: "Lax",
      },
    ]);
    const api = await installSessionApiMock(page, {
      initialPrincipal: tenantPrincipal("Tenant Admin"),
    });
    await page.goto("/app/overview");

    await page.getByRole("button", { name: "Sign out" }).click();

    await expect(page).toHaveURL(/\/login$/);
    await expect(page.getByRole("status")).toContainText(
      "You have signed out securely.",
    );
    const logoutCall = api.calls.find((call) => call.method === "DELETE");
    expect(logoutCall?.headers["x-csrf-token"]).toBe("e2e-csrf-token");
    expect(logoutCall?.headers.cookie).toContain("mt_csrf=e2e-csrf-token");
  });

  test("redirects an expired session and announces why sign-in is required", async ({
    page,
  }) => {
    await installSessionApiMock(page, {
      initialPrincipal: platformPrincipal(),
    });
    await page.goto("/platform");
    await expect(
      page.getByRole("heading", { name: "Dashboard" }),
    ).toBeVisible();

    await page.evaluate(() => {
      window.dispatchEvent(new Event("workspace:session-expired"));
    });

    await expect(page).toHaveURL(/\/login$/);
    await expect(page.getByRole("status")).toContainText(
      "Your session has expired. Sign in again to continue.",
    );
  });

  test("stores only an explicitly remembered workspace, never credentials or tokens", async ({
    page,
  }) => {
    await installSessionApiMock(page, {
      loginPrincipal: tenantPrincipal("Employee"),
    });
    await page.goto("/login");

    await submitTenantLogin(page, true);
    await expect(page).toHaveURL("/app/my-work");

    const storage = await page.evaluate(() => ({
      local: Object.fromEntries(
        Array.from({ length: window.localStorage.length }, (_, index) => {
          const key = window.localStorage.key(index) ?? "";
          return [key, window.localStorage.getItem(key)];
        }),
      ),
      session: Object.fromEntries(
        Array.from({ length: window.sessionStorage.length }, (_, index) => {
          const key = window.sessionStorage.key(index) ?? "";
          return [key, window.sessionStorage.getItem(key)];
        }),
      ),
    }));

    expect(storage).toEqual({
      local: { "workspace.remembered-slug": "northstar-labs" },
      session: {},
    });
    expect(JSON.stringify(storage)).not.toContain(PASSWORD);
    expect(JSON.stringify(storage)).not.toContain("member@northstar.example");
    expect(JSON.stringify(storage).toLowerCase()).not.toContain("token");
    expect(JSON.stringify(storage).toLowerCase()).not.toContain("bearer");
  });

  test("exposes labeled controls, keyboard password visibility, and live validation", async ({
    page,
  }) => {
    const api = await installSessionApiMock(page);
    await page.goto("/login");

    const workspace = page.getByRole("textbox", {
      name: "Workspace",
      exact: true,
    });
    const email = page.getByRole("textbox", {
      name: "Work email",
      exact: true,
    });
    const password = page.locator("#tenant-password");
    await expect(page.getByRole("main")).toHaveCount(1);
    await expect(workspace).toHaveAccessibleDescription(
      "The unique name used by your organization.",
    );

    await workspace.focus();
    await page.keyboard.type("invalid--workspace");
    await email.fill("not-an-email");
    await password.fill("visible-value");
    const visibility = page.getByRole("button", { name: "Show password" });
    await visibility.focus();
    await page.keyboard.press("Enter");
    await expect(password).toHaveAttribute("type", "text");
    await expect(
      page.getByRole("button", { name: "Hide password" }),
    ).toHaveAttribute("aria-pressed", "true");

    await page.getByRole("button", { name: "Sign in to workspace" }).click();
    await expect(
      page.getByText("Use lowercase letters, numbers, and single hyphens only."),
    ).toBeVisible();
    await expect(page.getByText("Enter a valid email address.")).toBeVisible();
    expect(api.calls.filter((call) => call.method === "POST")).toHaveLength(0);
  });
});
