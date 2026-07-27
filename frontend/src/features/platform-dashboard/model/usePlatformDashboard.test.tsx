import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { NetworkError } from "../../../shared/api/errors";
import { platformDashboardApi } from "../api/platform-dashboard-api";
import type { PlatformDashboard } from "./dashboard";
import { usePlatformDashboard } from "./usePlatformDashboard";

vi.mock("../api/platform-dashboard-api", () => ({
  platformDashboardApi: {
    getDashboard: vi.fn(),
    getReadiness: vi.fn(),
  },
}));

const dashboard: PlatformDashboard = {
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
    tenant_growth: [],
    new_registrations: [],
    subscription_distribution: [],
  },
  recent_activity: [],
};

const Probe = () => {
  const state = usePlatformDashboard({
    growthMonths: 12,
    registrationDays: 30,
  });

  return (
    <div>
      <span>{state.data?.kpis.total_tenants ?? "no data"}</span>
      <span>{state.error ?? "no error"}</span>
      <span>{state.health}</span>
      <button type="button" onClick={() => void state.refresh()}>
        refresh
      </button>
    </div>
  );
};

describe("usePlatformDashboard", () => {
  afterEach(() => {
    vi.clearAllMocks();
  });

  it("loads dashboard and readiness data with bounded defaults", async () => {
    vi.mocked(platformDashboardApi.getDashboard).mockResolvedValue(dashboard);
    vi.mocked(platformDashboardApi.getReadiness).mockResolvedValue({
      checkedAt: dashboard.generated_at,
      status: "healthy",
    });

    render(<Probe />);

    expect(await screen.findByText("18")).toBeVisible();
    expect(screen.getByText("healthy")).toBeVisible();
    expect(platformDashboardApi.getDashboard).toHaveBeenCalledWith(
      { activityLimit: 10, growthMonths: 12, registrationDays: 30 },
      expect.any(AbortSignal),
    );
  });

  it("preserves the last successful data when a refresh fails", async () => {
    vi.mocked(platformDashboardApi.getDashboard)
      .mockResolvedValueOnce(dashboard)
      .mockRejectedValueOnce(new NetworkError());
    vi.mocked(platformDashboardApi.getReadiness).mockResolvedValue({
      checkedAt: dashboard.generated_at,
      status: "healthy",
    });

    render(<Probe />);
    expect(await screen.findByText("18")).toBeVisible();

    fireEvent.click(screen.getByRole("button", { name: "refresh" }));

    await waitFor(() =>
      expect(
        screen.getByText(/dashboard service could not be reached/i),
      ).toBeVisible(),
    );
    expect(screen.getByText("18")).toBeVisible();
  });

  it("updates health independently when a dashboard refresh fails", async () => {
    vi.mocked(platformDashboardApi.getDashboard)
      .mockResolvedValueOnce(dashboard)
      .mockRejectedValueOnce(new NetworkError());
    vi.mocked(platformDashboardApi.getReadiness)
      .mockResolvedValueOnce({
        checkedAt: dashboard.generated_at,
        status: "healthy",
      })
      .mockResolvedValueOnce({
        checkedAt: null,
        status: "degraded",
      });

    render(<Probe />);
    expect(await screen.findByText("healthy")).toBeVisible();

    fireEvent.click(screen.getByRole("button", { name: "refresh" }));

    expect(await screen.findByText("degraded")).toBeVisible();
    expect(screen.getByText("18")).toBeVisible();
  });
});
