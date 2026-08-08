import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import {
  fetchTemplateDetail,
  previewTemplate,
  resetTemplateOverride,
  saveTemplateOverride,
} from "../../features/configurations/api/configuration-api";
import type { ConfigTemplateDetailResponse } from "../../features/configurations/model/types";
import { ConfigTemplateEditorPage } from "./ConfigTemplateEditorPage";

vi.mock("../../features/configurations/api/configuration-api", () => ({
  fetchTemplateDetail: vi.fn(),
  previewTemplate: vi.fn(),
  resetTemplateOverride: vi.fn(),
  saveTemplateOverride: vi.fn(),
}));

const templateId = "33333333-3333-4333-8333-333333333333";

const detail = (
  subject: string | null,
  body: string,
  description = "Initial platform description",
  defaultSubject: string | null = subject,
): ConfigTemplateDetailResponse => ({
  template_id: templateId,
  category_id: "11111111-1111-4111-8111-111111111111",
  code: "core_hr_welcome",
  display_name: "Welcome email",
  description,
  template_type: "EMAIL",
  subject,
  body,
  placeholders: [
    {
      key: "employee_name",
      label: "Employee name",
      sample_value: "Ada",
      required: true,
    },
  ],
  metadata: {},
  is_active: true,
  sort_order: 10,
  is_customized: false,
  default_subject: defaultSubject,
  default_body: body,
});

const renderPage = () =>
  render(
    <MemoryRouter initialEntries={[`/app/configurations/templates/${templateId}`]}>
      <Routes>
        <Route
          path="/app/configurations/templates/:templateId"
          element={<ConfigTemplateEditorPage />}
        />
      </Routes>
    </MemoryRouter>,
  );

describe("ConfigTemplateEditorPage focus refresh", () => {
  beforeEach(() => {
    vi.resetAllMocks();
    vi.mocked(fetchTemplateDetail)
      .mockResolvedValueOnce(detail("Initial subject", "Initial body"))
      .mockResolvedValueOnce(detail("Updated subject", "Updated body"))
      .mockResolvedValue(
        detail("Newest subject", "Newest body", "Newest platform description"),
      );
    vi.mocked(previewTemplate).mockResolvedValue({ subject: null, rendered_body: "" });
    vi.mocked(resetTemplateOverride).mockResolvedValue(detail("Reset subject", "Reset body"));
    vi.mocked(saveTemplateOverride).mockResolvedValue(detail("Saved subject", "Saved body"));
  });

  it("applies fresh effective content on focus without overwriting an unsaved draft", async () => {
    renderPage();

    expect(await screen.findByLabelText("Subject Line")).toHaveValue("Initial subject");

    act(() => window.dispatchEvent(new Event("focus")));

    await waitFor(() => {
      expect(screen.getByLabelText("Subject Line")).toHaveValue("Updated subject");
      expect(screen.getByLabelText("Template Body (Markdown)")).toHaveValue("Updated body");
    });

    fireEvent.change(screen.getByLabelText("Template Body (Markdown)"), {
      target: { value: "Unsaved tenant draft" },
    });
    act(() => window.dispatchEvent(new Event("focus")));

    await waitFor(() => expect(fetchTemplateDetail).toHaveBeenCalledTimes(3));
    expect(await screen.findByText("Newest platform description")).toBeVisible();
    expect(screen.getByLabelText("Template Body (Markdown)")).toHaveValue(
      "Unsaved tenant draft",
    );
    expect(screen.getByLabelText("Subject Line")).toHaveValue("Updated subject");
    expect(fetchTemplateDetail).toHaveBeenLastCalledWith(templateId);
  });

  it("keeps a subject-capable template editable after the tenant clears its subject", async () => {
    vi.mocked(saveTemplateOverride).mockResolvedValue(
      detail(null, "Saved body", "Initial platform description", "Initial subject"),
    );
    renderPage();

    const subject = await screen.findByLabelText("Subject Line");
    fireEvent.change(subject, { target: { value: "" } });
    fireEvent.click(screen.getByRole("button", { name: "Save Changes" }));

    await waitFor(() => expect(saveTemplateOverride).toHaveBeenCalledWith(
      templateId,
      expect.objectContaining({ subject: null }),
    ));
    expect(await screen.findByLabelText("Subject Line")).toHaveValue("");
    fireEvent.change(screen.getByLabelText("Subject Line"), {
      target: { value: "Restored tenant subject" },
    });
    expect(screen.getByLabelText("Subject Line")).toHaveValue("Restored tenant subject");
  });

  it("keeps a snapshotted tenant subject visible after the platform removes its default", async () => {
    vi.mocked(fetchTemplateDetail).mockReset().mockResolvedValue(
      detail("Tenant subject", "Tenant body", "Customized template", null),
    );
    renderPage();

    expect(await screen.findByLabelText("Subject Line")).toHaveValue("Tenant subject");
  });
});
