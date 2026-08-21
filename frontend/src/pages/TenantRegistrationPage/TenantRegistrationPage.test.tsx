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
    vi.mocked(tenantsApi.create).mockReset();
  });

  it("uses the renamed company identifiers and requires PAN and designation", async () => {
    renderPage();

    expect(await screen.findByLabelText("Tax Registration number")).toBeVisible();
    expect(screen.getByLabelText("PAN number *")).toBeRequired();
    expect(screen.getByLabelText("Designation *")).toBeRequired();
    expect(screen.queryByLabelText("Registration number")).not.toBeInTheDocument();
    expect(screen.queryByLabelText("Tax identifier")).not.toBeInTheDocument();
    expect(screen.queryByText("Workspace access")).not.toBeInTheDocument();
    expect(screen.queryByLabelText(/Workspace slug/i)).not.toBeInTheDocument();
    expect(screen.queryByLabelText(/Temporary password/i)).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Add alternate contact" }));
    expect(screen.getAllByLabelText("Designation *")).toHaveLength(2);
    expect(screen.getAllByLabelText("Designation *")[1]).toBeRequired();

    fireEvent.change(screen.getByLabelText("PAN number *"), {
      target: { value: "invalid" },
    });
    fireEvent.click(screen.getAllByRole("button", { name: "Register tenant" })[0]);

    expect(await screen.findByText(/Enter a valid PAN/)).toBeVisible();
    expect(screen.getByText("Designation is required")).toBeVisible();
    expect(tenantsApi.create).not.toHaveBeenCalled();
  });

  it("submits the renamed fields with an uppercase PAN", async () => {
    vi.mocked(tenantsApi.create).mockResolvedValue({
      org_name: "Acme Corporation",
    } as never);
    renderPage();
    await screen.findByLabelText("Tenant name *");

    const fill = (label: string, value: string) => {
      fireEvent.change(screen.getByLabelText(label), { target: { value } });
    };

    fill("Tenant name *", "Acme Corporation");
    fill("Tenant code *", "acme");
    fill("Legal company name *", "Acme Corporation Private Limited");
    fill("Industry *", "Technology");
    fill("Company size *", "51-200 employees");
    fill("Tax Registration number", "  TAX-REG-42  ");
    fill("PAN number *", "abcde1234f");
    fill("Address line 1 *", "1 Market Street");
    fill("City *", "Bengaluru");
    fill("State / province *", "Karnataka");
    fill("Country *", "India");
    fill("Postal / ZIP code *", "560001");
    fill("Contact person *", "Avery Morgan");
    fill("Designation *", "Operations Director");
    fill("Contact email *", "avery@example.com");
    fill("Phone number *", "+91 99999 99999");
    fireEvent.click(screen.getByRole("button", { name: "Add alternate contact" }));
    fireEvent.change(screen.getAllByLabelText("Contact person *")[1], {
      target: { value: "Jordan Lee" },
    });
    fireEvent.change(screen.getAllByLabelText("Designation *")[1], {
      target: { value: "Finance Manager" },
    });
    fireEvent.change(screen.getAllByLabelText("Contact email *")[1], {
      target: { value: "jordan@example.com" },
    });
    fireEvent.change(screen.getAllByLabelText("Phone number *")[1], {
      target: { value: "+91 88888 88888" },
    });
    fireEvent.click(screen.getByLabelText("Select Core HR"));
    fireEvent.click(screen.getAllByRole("button", { name: "Register tenant" })[0]);

    await waitFor(() => expect(tenantsApi.create).toHaveBeenCalledTimes(1));
    expect(tenantsApi.create).toHaveBeenCalledWith(expect.objectContaining({
      tax_registration_number: "TAX-REG-42",
      pan_number: "ABCDE1234F",
      contact_designation: "Operations Director",
      alternate_contact_designation: "Finance Manager",
    }));
    const submitted = vi.mocked(tenantsApi.create).mock.calls[0]?.[0];
    expect(submitted).not.toHaveProperty("registration_number");
    expect(submitted).not.toHaveProperty("tax_identifier");
    expect(submitted).not.toHaveProperty("workspace_slug");
    expect(submitted).not.toHaveProperty("tenant_admin_email");
    expect(submitted).not.toHaveProperty("tenant_admin_password");
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
