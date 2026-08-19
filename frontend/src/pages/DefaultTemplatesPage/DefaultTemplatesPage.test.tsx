import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { defaultTemplatesApi } from "../../features/default-template-management/api/default-templates-api";
import { offeringsApi } from "../../features/offering-management/api/offerings-api";
import { DefaultTemplatesPage } from "./DefaultTemplatesPage";

vi.mock("../../features/default-template-management/api/default-templates-api", () => ({
  defaultTemplatesApi: {
    list: vi.fn(),
  },
}));

vi.mock("../../features/offering-management/api/offerings-api", () => ({
  offeringsApi: {
    list: vi.fn(),
  },
}));

const coreHrId = "11111111-1111-4111-8111-111111111111";

const offerings = [
  {
    offering_id: coreHrId,
    code: "CORE_HR",
    display_name: "Core HR",
    description: "People operations.",
    icon_key: "users",
    route_slug: "core-hr",
    sort_order: 10,
    status: "ACTIVE" as const,
    tenant_entitlement_count: 4,
    configuration_category_count: 2,
  },
  {
    offering_id: "22222222-2222-4222-8222-222222222222",
    code: "FUTURE_PAYROLL",
    display_name: "Future Payroll",
    description: "Payroll workflows.",
    icon_key: "wallet",
    route_slug: "future-payroll",
    sort_order: 20,
    status: "INACTIVE" as const,
    tenant_entitlement_count: 0,
    configuration_category_count: 0,
  },
];

const template = {
  template_id: "33333333-3333-4333-8333-333333333333",
  offering_id: coreHrId,
  offering_code: "CORE_HR",
  offering_name: "Core HR",
  category_id: "44444444-4444-4444-8444-444444444444",
  category_code: "corehr_letter_templates",
  category_name: "Letter Templates",
  code: "core_hr_offer_letter",
  name: "Offer Letter",
  description: "Employment offer.",
  type: "LETTER" as const,
  subject: "Your offer",
  sort_order: 10,
  is_active: true,
  version: 2,
  created_at: "2026-08-06T00:00:00Z",
  updated_at: "2026-08-06T00:00:00Z",
  inheriting_tenant_count: 3,
  customized_tenant_count: 1,
};

describe("DefaultTemplatesPage", () => {
  beforeEach(() => {
    vi.mocked(offeringsApi.list).mockResolvedValue(offerings);
    vi.mocked(defaultTemplatesApi.list).mockResolvedValue([template]);
  });

  it("auto-selects the first offering and carries URL filters into create", async () => {
    const LocationProbe = () => {
      const location = useLocation();
      return <output data-testid="location-search">{location.search}</output>;
    };
    render(
      <MemoryRouter initialEntries={["/platform/default-templates?type=LETTER"]} future={{ v7_relativeSplatPath: true, v7_startTransition: true }}>
        <Routes><Route path="/platform/default-templates" element={<DefaultTemplatesPage />} /></Routes>
        <LocationProbe />
      </MemoryRouter>,
    );

    await waitFor(
      () => expect(screen.getByTestId("location-search")).toHaveTextContent(`offering_id=${coreHrId}`),
      { timeout: 5_000 },
    );
    expect(await screen.findByRole("heading", { name: "Core HR" }, { timeout: 5_000 })).toBeVisible();
    expect(screen.getByRole("button", { name: "Letter" })).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByRole("link", { name: "New default template" })).toHaveAttribute(
      "href",
      `/platform/default-templates/new?offering_id=${coreHrId}&type=LETTER`,
    );
    expect(defaultTemplatesApi.list).toHaveBeenCalledWith(expect.objectContaining({ offeringId: coreHrId }));
  }, 15_000);

  it("shows inactive offerings and exposes template types as filter chips", async () => {
    const user = userEvent.setup();
    const LocationProbe = () => {
      const location = useLocation();
      return <output data-testid="location-search">{location.search}</output>;
    };
    render(
      <MemoryRouter initialEntries={[`/platform/default-templates?offering_id=${coreHrId}`]} future={{ v7_relativeSplatPath: true, v7_startTransition: true }}>
        <Routes><Route path="/platform/default-templates" element={<DefaultTemplatesPage />} /></Routes>
        <LocationProbe />
      </MemoryRouter>,
    );

    expect(await screen.findByRole("button", { name: /Future Payroll/ })).toHaveTextContent("Inactive");
    expect(screen.getByRole("button", { name: "All" })).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByRole("button", { name: "Email" })).toBeVisible();
    expect(screen.getByRole("button", { name: "Notification" })).toBeVisible();

    await user.click(screen.getByRole("button", { name: "Letter" }));
    expect(screen.getByTestId("location-search")).toHaveTextContent("type=LETTER");
    expect(await screen.findByRole("link", { name: /Offer Letter/ })).toBeVisible();
  });
});
