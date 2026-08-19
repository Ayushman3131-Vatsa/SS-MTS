import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { tenantsApi } from "../../features/tenant-management/api/tenants-api";
import type { TenantRegistrationOptions } from "../../features/tenant-management/model/tenants";
import { TenantRegistrationPage } from "./TenantRegistrationPage";

vi.mock("../../features/tenant-management/api/tenants-api", () => ({
  tenantsApi: {
    getRegistrationOptions: vi.fn(),
    create: vi.fn(),
  },
}));

const options: TenantRegistrationOptions = {
  plans: [{
    code: "BASIC",
    display_name: "Basic",
    price: null,
    currency: null,
    billing_interval: null,
    max_users: null,
    requires_end_date: false,
  }],
  offerings: [
    {
      offering_id: "11111111-1111-4111-8111-111111111111",
      code: "CORE_HR",
      display_name: "Core HR",
      description: "People records and workforce operations.",
      icon_key: "package",
      route_slug: "core-hr",
      sort_order: 1,
    },
    {
      offering_id: "22222222-2222-4222-8222-222222222222",
      code: "HELP_DESK",
      display_name: "Help Desk",
      description: "Internal support requests and service tracking.",
      icon_key: "package",
      route_slug: "help-desk",
      sort_order: 2,
    },
  ],
  statuses: ["ACTIVE"],
  database_modes: ["SHARED"],
  defaults: {
    subscription_plan_code: "BASIC",
    status: "ACTIVE",
    database_mode: "SHARED",
  },
};

const renderPage = () => render(
  <MemoryRouter>
    <TenantRegistrationPage />
  </MemoryRouter>,
);

describe("TenantRegistrationPage offering access workflow", () => {
  beforeEach(() => {
    vi.mocked(tenantsApi.getRegistrationOptions).mockResolvedValue(options);
  });

  it("separates offering selection from clearly labelled access windows", async () => {
    renderPage();

    fireEvent.click(await screen.findByLabelText("Select Core HR"));

    const startsInput = screen.getByLabelText("Core HR access starts");
    const expiresInput = screen.getByLabelText("Core HR access expires");
    expect(screen.getByText("Configure access windows")).toBeVisible();
    expect(startsInput).toBeVisible();
    expect(expiresInput).toBeVisible();
    expect(expiresInput).toBeRequired();
    expect(expiresInput).toHaveAttribute("min", startsInput.getAttribute("value"));
    expect(screen.getByText("1 selected")).toBeVisible();
  });

  it("removes a configured offering and restores defaults when reset", async () => {
    renderPage();

    fireEvent.click(await screen.findByLabelText("Select Core HR"));
    fireEvent.click(screen.getByRole("button", { name: "Remove Core HR" }));
    expect(screen.queryByLabelText("Core HR access starts")).not.toBeInTheDocument();
    expect(screen.getByText("No offerings selected")).toBeVisible();

    fireEvent.click(screen.getByLabelText("Select Help Desk"));
    fireEvent.click(screen.getByRole("button", { name: "Reset" }));

    await waitFor(() => expect(screen.getByLabelText("Select Help Desk")).not.toBeChecked());
    expect(screen.queryByLabelText("Help Desk access starts")).not.toBeInTheDocument();
  });
});
