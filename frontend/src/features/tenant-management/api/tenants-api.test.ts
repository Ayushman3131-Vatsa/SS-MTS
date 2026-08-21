import { afterEach, describe, expect, it, vi } from "vitest";

import { tenantsApi } from "./tenants-api";

const response = (body: unknown) =>
  new Response(JSON.stringify(body), {
    status: 200,
    headers: { "Content-Type": "application/json" },
  });

const tenant = {
  tenant_id: "11111111-1111-4111-8111-111111111111",
  org_name: "Acme",
  tenant_code: "ACME",
  legal_name: null,
  industry: null,
  company_size: null,
  website: null,
  tax_registration_number: null,
  pan_number: null,
  address_line_1: null,
  address_line_2: null,
  city: null,
  state_province: null,
  country: null,
  postal_code: null,
  contact_name: null,
  contact_designation: null,
  alternate_contact_designation: null,
  contact_email: null,
  contact_phone: null,
  subscription_plan: "Free",
  subscription_plan_code: "FREE",
  subscription_ends_at: null,
  status: "ACTIVE",
  database_mode: "SHARED",
  database_provisioning_state: "READY",
  user_count: 1,
  offerings: [],
  created_by_admin_id: "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
  created_at: "2026-08-05T00:00:00Z",
  updated_at: "2026-08-05T00:00:00Z",
  version: 2,
};

const entitlement = {
  offering_id: "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb",
  code: "TASK_MANAGEMENT",
  display_name: "Task Management",
  description: "Projects and tasks.",
  icon_key: "check-square",
  route_slug: "tasks",
  sort_order: 10,
  entitlement_id: "cccccccc-cccc-4ccc-8ccc-cccccccccccc",
  status: "ACTIVE",
  starts_at: "2026-08-05T00:00:00Z",
  ends_at: "2026-09-05T00:00:00Z",
  suspended_at: null,
  deactivated_at: null,
  reason: null,
  version: 1,
  created_at: "2026-08-05T00:00:00Z",
  updated_at: "2026-08-05T00:00:00Z",
};

describe("tenantsApi registration options", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("normalizes Decimal plan prices serialized by Pydantic", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      response({
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
        offerings: [
          {
            offering_id: "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
            code: "CORE_HR",
            display_name: "Core HR",
            description: "People records.",
            icon_key: "users",
            route_slug: "core-hr",
            sort_order: 10,
          },
        ],
        statuses: ["ACTIVE", "SUSPENDED"],
        database_modes: ["SHARED", "DEDICATED"],
        defaults: {
          subscription_plan_code: "FREE",
          status: "ACTIVE",
          database_mode: "SHARED",
        },
      }),
    );

    const options = await tenantsApi.getRegistrationOptions();

    expect(options.plans[0]?.price).toBe(0);
    expect(options.offerings[0]?.route_slug).toBe("core-hr");
  });

  it("passes server-side pagination and filters", async () => {
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValue(response({ items: [tenant], page: 2, page_size: 10, total: 11 }));

    const result = await tenantsApi.list({
      page: 2,
      pageSize: 10,
      query: "acme",
      status: "SUSPENDED",
    });

    const requestUrl = String(fetchMock.mock.calls[0]?.[0]);
    expect(requestUrl).toContain("page=2");
    expect(requestUrl).toContain("page_size=10");
    expect(requestUrl).toContain("query=acme");
    expect(requestUrl).toContain("status=SUSPENDED");
    expect(result.total).toBe(11);
  });

  it("sends an idempotency key for offering grants", async () => {
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValue(response(entitlement));

    await tenantsApi.grant("11111111-1111-4111-8111-111111111111", {
      offering_id: entitlement.offering_id,
      starts_at: entitlement.starts_at,
      ends_at: entitlement.ends_at,
      expected_tenant_version: 2,
      reason: "Scheduled access",
    });

    const init = fetchMock.mock.calls[0]?.[1] as RequestInit | undefined;
    expect(new Headers(init?.headers).get("Idempotency-Key")).toBeTruthy();
    expect(JSON.parse(String(init?.body))).toMatchObject({
      expected_tenant_version: 2,
      reason: "Scheduled access",
    });
  });

  it("hard-deletes retired entitlements with version and reason", async () => {
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValue(new Response(null, { status: 204 }));

    await tenantsApi.removeEntitlement(
      tenant.tenant_id,
      entitlement.entitlement_id,
      { expected_version: 3, reason: "Retention cleanup" },
    );

    const [url, init] = fetchMock.mock.calls[0] ?? [];
    expect(String(url)).toContain(`/offering-entitlements/${entitlement.entitlement_id}`);
    expect(init?.method).toBe("DELETE");
    expect(JSON.parse(String(init?.body))).toEqual({
      expected_version: 3,
      reason: "Retention cleanup",
    });
  });
});
