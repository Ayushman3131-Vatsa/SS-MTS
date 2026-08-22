import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { tenantsApi } from "../../features/tenant-management/api/tenants-api";
import type { TenantOfferingEntitlement, TenantRecord } from "../../features/tenant-management/model/tenants";
import { TenantDetailPage } from "./TenantDetailPage";

vi.mock("../../features/tenant-management/api/tenants-api", () => ({
  tenantsApi: {
    get: vi.fn(),
    catalog: vi.fn(),
    grant: vi.fn(),
  tenantAction: vi.fn(),
    enable: vi.fn(),
    regenerateInitialPassword: vi.fn(),
    offeringAction: vi.fn(),
    removeEntitlement: vi.fn(),
  },
}));

const entitlement = (
  name: string,
  status: string,
  sequence: number,
  endsAt: string | null = "2026-09-05T12:00:00Z",
): TenantOfferingEntitlement => ({
  offering_id: `11111111-1111-4111-8111-11111111111${sequence}`,
  code: name.toUpperCase().replaceAll(" ", "_"),
  display_name: name,
  description: `${name} description`,
  icon_key: "package",
  route_slug: name.toLowerCase().replaceAll(" ", "-"),
  sort_order: sequence,
  entitlement_id: `22222222-2222-4222-8222-22222222222${sequence}`,
  status,
  starts_at: "2026-08-05T12:00:00Z",
  ends_at: endsAt,
  suspended_at: status === "SUSPENDED" ? "2026-08-06T12:00:00Z" : null,
  deactivated_at: status === "DEACTIVATED" ? "2026-08-07T12:00:00Z" : null,
  reason: null,
  version: 1,
  created_at: "2026-08-05T12:00:00Z",
  updated_at: "2026-08-05T12:00:00Z",
});

const offerings = [
  entitlement("Active Offering", "ACTIVE", 1, null),
  entitlement("Suspended Offering", "SUSPENDED", 2),
  entitlement("Deactivated Offering", "DEACTIVATED", 3),
  entitlement("Expired Offering", "EXPIRED", 4),
];

const tenant: TenantRecord = {
  tenant_id: "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
  org_name: "Example Tenant",
  tenant_code: "EXAMPLE",
  legal_name: null,
  industry: null,
  company_size: null,
  website: null,
  tax_registration_number: null,
  pan_number: "ABCDE1234F",
  address_line_1: null,
  address_line_2: null,
  city: null,
  state_province: null,
  country: null,
  postal_code: null,
  contact_name: "Avery Morgan",
  contact_designation: "Operations Director",
  contact_email: null,
  contact_phone: null,
  tenant_admin_provisioning_status: "NOT_ENABLED",
  alternate_contact_name: "Jordan Lee",
  alternate_contact_designation: "Finance Manager",
  alternate_contact_email: "jordan@example.com",
  alternate_contact_phone: "+91 88888 88888",
  subscription_plan: "Basic",
  subscription_plan_code: "BASIC",
  subscription_ends_at: null,
  status: "ACTIVE",
  database_mode: "SHARED",
  database_provisioning_state: "READY",
  user_count: 1,
  offerings,
  created_by_admin_id: "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb",
  created_at: "2026-08-05T12:00:00Z",
  updated_at: "2026-08-05T12:00:00Z",
  version: 1,
};

const renderPage = () => render(
  <MemoryRouter initialEntries={[`/platform/tenants/${tenant.tenant_id}`]}>
    <Routes>
      <Route path="/platform/tenants/:tenantId" element={<TenantDetailPage />} />
    </Routes>
  </MemoryRouter>,
);

describe("TenantDetailPage entitlement management", () => {
  beforeEach(() => {
    vi.mocked(tenantsApi.get).mockResolvedValue(tenant);
    vi.mocked(tenantsApi.catalog).mockResolvedValue([]);
    vi.mocked(tenantsApi.removeEntitlement).mockResolvedValue(undefined);
  });

  it("groups offerings into accessible status tabs", async () => {
    renderPage();

    const activeTab = await screen.findByRole("tab", { name: "Active 1" });
    expect(activeTab).toHaveAttribute("aria-selected", "true");
    expect(within(screen.getByRole("tabpanel")).getByText("Active Offering")).toBeVisible();
    expect(screen.getByText("Legacy: no expiry")).toBeVisible();

    fireEvent.click(screen.getByRole("tab", { name: "Suspended 1" }));
    expect(within(screen.getByRole("tabpanel")).getByText("Suspended Offering")).toBeVisible();
    expect(screen.queryByText("Active Offering")).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("tab", { name: "Deactivated 2" }));
    const historyPanel = within(screen.getByRole("tabpanel"));
    expect(historyPanel.getByText("Deactivated Offering")).toBeVisible();
    expect(historyPanel.getByText("Expired Offering")).toBeVisible();
  });

  it("displays the primary contact designation", async () => {
    renderPage();

    expect(await screen.findByText("Operations Director")).toBeVisible();
    expect(screen.getByText("Finance Manager")).toBeVisible();
  });

  it("requires an expiry date when granting an offering", async () => {
    renderPage();

    expect(await screen.findByLabelText("Expires")).toBeRequired();
  });

  it("requires confirmation and a reason before permanently removing history", async () => {
    renderPage();

    fireEvent.click(await screen.findByRole("tab", { name: "Deactivated 2" }));
    fireEvent.click(within(screen.getByRole("tabpanel")).getAllByRole("button", { name: "Remove" })[0]);

    expect(screen.getByRole("dialog", { name: "Remove offering?" })).toBeVisible();
    fireEvent.change(screen.getByLabelText("Reason for permanent removal *"), {
      target: { value: "Duplicate historical record" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Remove permanently" }));

    await waitFor(() => expect(tenantsApi.removeEntitlement).toHaveBeenCalledWith(
      tenant.tenant_id,
      offerings[2].entitlement_id,
      { expected_version: 1, reason: "Duplicate historical record" },
    ));
  });
});
