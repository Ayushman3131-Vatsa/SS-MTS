import { describe, expect, it } from "vitest";

import { parseDashboard, parseReadiness } from "./dashboard";

const dashboardPayload = {
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
      activity_id: "11111111-1111-4111-8111-111111111111",
      event_type: "TENANT_CREATED",
      occurred_at: "2026-07-23T12:00:00Z",
      tenant: {
        tenant_id: "22222222-2222-4222-8222-222222222222",
        tenant_name: "Northstar Labs",
      },
      metadata: {},
    },
  ],
};

describe("platform dashboard response parsing", () => {
  it("accepts the backend contract and forward-compatible catalog codes", () => {
    const result = parseDashboard({
      ...dashboardPayload,
      charts: {
        ...dashboardPayload.charts,
        subscription_distribution: [
          {
            plan_code: "GROWTH_2027",
            plan_name: "Growth",
            tenant_count: 3,
          },
        ],
      },
      recent_activity: [
        {
          ...dashboardPayload.recent_activity[0],
          event_type: "OFFERING_GRANTED",
          metadata: {
            offering: { display_name: "Payroll" },
          },
        },
      ],
    });

    expect(result.kpis.total_tenants).toBe(18);
    expect(result.charts.subscription_distribution[0]?.plan_code).toBe(
      "GROWTH_2027",
    );
    expect(result.recent_activity[0]?.event_type).toBe("OFFERING_GRANTED");
  });

  it("rejects negative metrics and malformed chart dates", () => {
    expect(() =>
      parseDashboard({
        ...dashboardPayload,
        kpis: { ...dashboardPayload.kpis, total_tenants: -1 },
      }),
    ).toThrow();
    expect(() =>
      parseDashboard({
        ...dashboardPayload,
        charts: {
          ...dashboardPayload.charts,
          tenant_growth: [{ month: "July", total_tenants: 4 }],
        },
      }),
    ).toThrow();
    expect(() =>
      parseDashboard({
        ...dashboardPayload,
        recent_activity: [
          { ...dashboardPayload.recent_activity[0], event_type: "offering-granted" },
        ],
      }),
    ).toThrow();
  });

  it("validates readiness without accepting infrastructure details", () => {
    expect(
      parseReadiness({
        status: "healthy",
        checked_at: "2026-07-23T12:30:00Z",
        checks: { api: "healthy", database: "healthy" },
      }).status,
    ).toBe("healthy");
  });
});

