import { afterEach, describe, expect, it, vi } from "vitest";

import { tenantsApi } from "./tenants-api";

const response = (body: unknown) =>
  new Response(JSON.stringify(body), {
    status: 200,
    headers: { "Content-Type": "application/json" },
  });

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
});
