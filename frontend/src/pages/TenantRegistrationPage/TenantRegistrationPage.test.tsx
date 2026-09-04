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

  it("submits selected offerings without manual access windows", async () => {
    vi.mocked(tenantsApi.getRegistrationOptions).mockResolvedValue({
      ...options,
      offerings: [options.offerings[0]],
    });
    vi.mocked(tenantsApi.create).mockResolvedValue({
      org_name: "Solo Corp",
      tenant_id: "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
      first_access: {
        email: "avery@example.com",
        username: "avery.morgan",
        temporary_password: "TempPass1!",
        login_path: "/SOLO/login",
        password_change_required: true,
        smartskale_access: {
          email: "hrms.support@smartskale.com",
          username: "ss_SOLO_admin",
          temporary_password: "Smartskale123!",
          login_path: "/SOLO/login",
          password_change_required: true,
        },
      },
    } as never);
    renderPage();
    await screen.findByLabelText("Tenant name *");

    const fill = (label: string, value: string) => {
      fireEvent.change(screen.getByLabelText(label), { target: { value } });
    };
    fill("Tenant name *", "Solo Corp");
    fill("Tenant code *", "solo");
    fill("Legal company name *", "Solo Corp Private Limited");
    fill("Industry *", "Technology");
    fill("Company size *", "10");
    fill("PAN number *", "ABCDE1234F");
    fill("Address line 1 *", "1 Market Street");
    fill("City *", "Bengaluru");
    fill("State / province *", "Karnataka");
    fill("Country *", "India");
    fill("Postal / ZIP code *", "560001");
    fill("Contact person *", "Avery Morgan");
    fill("Designation *", "Operations Director");
    fill("Contact email *", "avery@example.com");
    fill("Phone number *", "+91 99999 99999");
    fireEvent.click(screen.getByLabelText("Select Core HR"));
    fireEvent.click(screen.getAllByRole("button", { name: "Register tenant" })[0]);

    await waitFor(() => expect(tenantsApi.create).toHaveBeenCalledTimes(1));
    expect(await screen.findByText("Solo Corp is ready")).toBeVisible();
    expect(screen.getByText("avery@example.com")).toBeVisible();
    expect(screen.getByText("avery.morgan")).toBeVisible();
    expect(screen.getByText(/Sign-in URL: \/SOLO\/login/)).toBeVisible();
    expect(screen.getByText("ss_SOLO_admin")).toBeVisible();
    const submitted = vi.mocked(tenantsApi.create).mock.calls[0]?.[0];
    expect(submitted?.offering_ids).toEqual([options.offerings[0].offering_id]);
    expect(submitted?.offering_grants ?? []).toEqual([]);
  });

  it("does not show the access window configuration panel", async () => {
    renderPage();

    fireEvent.click(await screen.findByLabelText("Select Core HR"));

    expect(screen.queryByText("Configure access windows")).not.toBeInTheDocument();
    expect(screen.queryByLabelText("Core HR access starts")).not.toBeInTheDocument();
    expect(screen.getByText("1 selected")).toBeVisible();
  });

  it("restores defaults when reset", async () => {
    renderPage();

    fireEvent.click(await screen.findByLabelText("Select Core HR"));
    fireEvent.click(screen.getByLabelText("Select Help Desk"));
    fireEvent.click(screen.getByRole("button", { name: "Reset" }));

    await waitFor(() => expect(screen.getByLabelText("Select Help Desk")).not.toBeChecked());
  });
});
