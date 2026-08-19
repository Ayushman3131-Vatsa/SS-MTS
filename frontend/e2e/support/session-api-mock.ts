import type { Page } from "@playwright/test";

export type TenantRole = "Tenant Admin" | "Project Manager" | "Employee";

export interface PlatformPrincipal {
  principal_type: "platform_admin";
  principal_id: string;
  name: string;
  email: string;
  role: "Platform Admin";
  tenant: null;
}

export interface TenantPrincipal {
  principal_type: "tenant_user";
  principal_id: string;
  name: string;
  email: string;
  role: TenantRole;
  tenant: {
    tenant_id: string;
    org_name: string;
    workspace_slug: string;
    status: "ACTIVE" | "SUSPENDED";
    offerings: Array<{
      offering_id: string;
      code: string;
      display_name: string;
      description: string;
      icon_key: string;
      route_slug: string;
      sort_order: number;
    }>;
  };
}

export type SessionPrincipal = PlatformPrincipal | TenantPrincipal;

interface LoginFailure {
  retryAfterSeconds?: number;
  status: 401 | 429 | 500;
}

interface SessionApiMockOptions {
  initialPrincipal?: SessionPrincipal | null;
  loginFailure?: LoginFailure;
  loginPrincipal?: SessionPrincipal;
}

export interface ApiCall {
  headers: Record<string, string>;
  method: string;
  path: string;
  payload: unknown;
  search?: string;
}

const JSON_HEADERS = {
  "Access-Control-Allow-Origin": "http://127.0.0.1:5173",
  "Content-Type": "application/json",
};

const PLATFORM_DASHBOARD = {
  generated_at: "2026-07-23T12:30:00Z",
  filters: { growth_months: 12, registration_days: 30 },
  kpis: {
    total_tenants: 18,
    active_tenants: 16,
    dedicated_databases: 4,
    shared_database_tenants: 12,
    total_users: 284,
    new_tenants_this_month: 3,
    expired_subscriptions: 2,
  },
  charts: {
    tenant_growth: [
      { month: "2026-06-01", total_tenants: 15 },
      { month: "2026-07-01", total_tenants: 18 },
    ],
    new_registrations: [
      { date: "2026-07-22", new_tenants: 1 },
      { date: "2026-07-23", new_tenants: 2 },
    ],
    subscription_distribution: [
      { plan_code: "FREE", plan_name: "Free", tenant_count: 6 },
      { plan_code: "PRO", plan_name: "Professional", tenant_count: 12 },
    ],
  },
  recent_activity: [
    {
      activity_id: "55555555-5555-4555-8555-555555555555",
      event_type: "TENANT_CREATED",
      occurred_at: "2026-07-23T12:00:00Z",
      tenant: {
        tenant_id: "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
        tenant_name: "Northstar Labs",
      },
      metadata: {},
    },
  ],
};

export const platformPrincipal = (): PlatformPrincipal => ({
  principal_type: "platform_admin",
  principal_id: "11111111-1111-4111-8111-111111111111",
  name: "Priya Operator",
  email: "priya@platform.example",
  role: "Platform Admin",
  tenant: null,
});

export const tenantPrincipal = (role: TenantRole): TenantPrincipal => ({
  principal_type: "tenant_user",
  principal_id:
    role === "Tenant Admin"
      ? "22222222-2222-4222-8222-222222222222"
      : role === "Project Manager"
        ? "33333333-3333-4333-8333-333333333333"
        : "44444444-4444-4444-8444-444444444444",
  name:
    role === "Tenant Admin"
      ? "Taylor Admin"
      : role === "Project Manager"
        ? "Morgan Manager"
        : "Emery Employee",
  email: `${role.toLowerCase().replace(" ", ".")}@northstar.example`,
  role,
  tenant: {
    tenant_id: "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
    org_name: "Northstar Labs",
    workspace_slug: "northstar-labs",
    status: "ACTIVE",
    offerings: [],
  },
});

export const installSessionApiMock = async (
  page: Page,
  options: SessionApiMockOptions = {},
) => {
  let currentPrincipal = options.initialPrincipal ?? null;
  const calls: ApiCall[] = [];

  await page.route(/\/api\/platform\/dashboard(?:\?.*)?$/, async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    calls.push({
      headers: request.headers(),
      method: request.method(),
      path: url.pathname,
      payload: null,
      search: url.search,
    });
    await route.fulfill({
      status: 200,
      headers: JSON_HEADERS,
      json: PLATFORM_DASHBOARD,
    });
  });

  await page.route(/\/api\/health\/ready$/, async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    calls.push({
      headers: request.headers(),
      method: request.method(),
      path: url.pathname,
      payload: null,
    });
    await route.fulfill({
      status: 200,
      headers: JSON_HEADERS,
      json: {
        status: "healthy",
        checked_at: "2026-07-23T12:30:00Z",
        checks: { api: "healthy", database: "healthy" },
      },
    });
  });

  await page.route(/\/api\/tenants(?:\?.*)?$/, async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    calls.push({
      headers: request.headers(),
      method: request.method(),
      path: url.pathname,
      payload: null,
      search: url.search,
    });
    await route.fulfill({
      status: 200,
      headers: JSON_HEADERS,
      json: { items: [], page: 1, page_size: 25, total: 0 },
    });
  });

  await page.route(/\/api\/tenants\/registration-options$/, async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    calls.push({
      headers: request.headers(),
      method: request.method(),
      path: url.pathname,
      payload: null,
    });
    await route.fulfill({
      status: 200,
      headers: JSON_HEADERS,
      json: {
        plans: [
          {
            code: "FREE",
            display_name: "Free",
            price: "0.00",
            currency: "USD",
            billing_interval: "MONTHLY",
            max_users: null,
            requires_end_date: false,
          },
        ],
        offerings: [],
        statuses: ["ACTIVE", "SUSPENDED"],
        database_modes: ["SHARED", "DEDICATED"],
        defaults: {
          subscription_plan_code: "FREE",
          status: "ACTIVE",
          database_mode: "SHARED",
        },
      },
    });
  });

  // A single `*` in a Playwright URL glob does not cross `/`, so it would
  // intercept `/session` but miss `/session/tenant` and `/session/platform`.
  // Use a regex that explicitly covers both the base resource and descendants.
  await page.route(/\/api\/auth\/session(?:\/.*)?$/, async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    const method = request.method();
    const postData = request.postData();
    const payload = postData ? request.postDataJSON() : null;

    calls.push({
      headers: request.headers(),
      method,
      path: url.pathname,
      payload,
    });

    if (method === "GET" && url.pathname === "/api/auth/session") {
      if (currentPrincipal) {
        await route.fulfill({
          status: 200,
          headers: JSON_HEADERS,
          json: currentPrincipal,
        });
      } else {
        await route.fulfill({
          status: 401,
          headers: JSON_HEADERS,
          json: { detail: "Authentication required" },
        });
      }
      return;
    }

    if (
      method === "POST" &&
      (url.pathname === "/api/auth/session/tenant" ||
        url.pathname === "/api/auth/session/platform")
    ) {
      if (options.loginFailure) {
        const headers: Record<string, string> = { ...JSON_HEADERS };
        if (options.loginFailure.retryAfterSeconds !== undefined) {
          headers["Retry-After"] = String(
            options.loginFailure.retryAfterSeconds,
          );
        }
        await route.fulfill({
          status: options.loginFailure.status,
          headers,
          json: { detail: "Invalid credentials" },
        });
        return;
      }

      if (!options.loginPrincipal) {
        await route.fulfill({
          status: 500,
          headers: JSON_HEADERS,
          json: { detail: "E2E mock login principal was not configured" },
        });
        return;
      }

      currentPrincipal = options.loginPrincipal;
      await route.fulfill({
        status: 200,
        headers: JSON_HEADERS,
        json: currentPrincipal,
      });
      return;
    }

    if (method === "DELETE" && url.pathname === "/api/auth/session") {
      currentPrincipal = null;
      await route.fulfill({ status: 204 });
      return;
    }

    await route.fulfill({
      status: 404,
      headers: JSON_HEADERS,
      json: { detail: "Unhandled E2E API route" },
    });
  });

  return { calls };
};
