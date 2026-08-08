import { act, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import {
  fetchCategoryTemplates,
  fetchConfigCategories,
} from "../../features/configurations/api/configuration-api";
import type {
  ConfigCategoryResponse,
  ConfigTemplateListItem,
} from "../../features/configurations/model/types";
import { ConfigurationsPage } from "./ConfigurationsPage";

vi.mock("../../features/configurations/api/configuration-api", () => ({
  fetchConfigCategories: vi.fn(),
  fetchCategoryTemplates: vi.fn(),
}));

const category: ConfigCategoryResponse = {
  category_id: "11111111-1111-4111-8111-111111111111",
  offering_id: "22222222-2222-4222-8222-222222222222",
  offering_code: "CORE_HR",
  offering_display_name: "Core HR",
  code: "core_hr_email_templates",
  display_name: "Email Templates",
  description: "Core HR email templates",
  icon_key: "mail",
  sort_order: 10,
  status: "ACTIVE",
  template_count: 1,
};

const template = (subject: string): ConfigTemplateListItem => ({
  template_id: "33333333-3333-4333-8333-333333333333",
  category_id: category.category_id,
  code: "core_hr_welcome",
  display_name: "Welcome email",
  description: "Welcomes a new employee",
  template_type: "EMAIL",
  subject,
  is_active: true,
  sort_order: 10,
  is_customized: false,
});

describe("ConfigurationsPage focus refresh", () => {
  beforeEach(() => {
    vi.mocked(fetchConfigCategories).mockResolvedValue([category]);
    vi.mocked(fetchCategoryTemplates)
      .mockResolvedValueOnce([template("Initial platform subject")])
      .mockResolvedValue([template("Updated platform subject")]);
  });

  it("refetches categories and effective templates when the window regains focus", async () => {
    render(
      <MemoryRouter>
        <ConfigurationsPage />
      </MemoryRouter>,
    );

    expect(await screen.findByText("Initial platform subject")).toBeVisible();

    act(() => window.dispatchEvent(new Event("focus")));

    expect(await screen.findByText("Updated platform subject")).toBeVisible();
    await waitFor(() => {
      expect(fetchConfigCategories).toHaveBeenCalledTimes(2);
      expect(fetchCategoryTemplates).toHaveBeenCalledTimes(2);
    });
    expect(fetchCategoryTemplates).toHaveBeenLastCalledWith(category.category_id);
  });
});
