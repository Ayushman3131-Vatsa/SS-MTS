import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { createMemoryRouter, RouterProvider } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { defaultTemplatesApi } from "../../features/default-template-management/api/default-templates-api";
import type { DefaultTemplateDetail } from "../../features/default-template-management/model/default-templates";
import { offeringsApi } from "../../features/offering-management/api/offerings-api";
import { ApiError } from "../../shared/api/errors";
import { DefaultTemplateEditorPage } from "./DefaultTemplateEditorPage";

vi.mock("../../features/default-template-management/api/default-templates-api", () => ({
  defaultTemplatesApi: {
    get: vi.fn(),
    create: vi.fn(),
    update: vi.fn(),
    preview: vi.fn(),
  },
}));

vi.mock("../../features/offering-management/api/offerings-api", () => ({
  offeringsApi: {
    list: vi.fn(),
  },
}));

const coreHrId = "11111111-1111-4111-8111-111111111111";
const payrollId = "22222222-2222-4222-8222-222222222222";
const templateId = "33333333-3333-4333-8333-333333333333";

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
    offering_id: payrollId,
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

const detail = {
  template_id: templateId,
  offering_id: coreHrId,
  offering_code: "CORE_HR",
  offering_name: "Core HR",
  category_id: "44444444-4444-4444-8444-444444444444",
  category_code: "corehr_email_templates",
  category_name: "Email Templates",
  code: "core_hr_welcome_email",
  name: "Welcome Email",
  description: "Sent to new employees.",
  type: "EMAIL" as const,
  subject: "Welcome, {{employee_name}}",
  body: "Hello {{employee_name}}",
  placeholders: [{
    key: "employee_name",
    label: "Employee name",
    sample_value: "Ada Lovelace",
    required: true,
  }],
  sort_order: 10,
  is_active: true,
  version: 3,
  created_at: "2026-08-06T00:00:00Z",
  updated_at: "2026-08-06T01:00:00Z",
  inheriting_tenant_count: 12,
  customized_tenant_count: 2,
};

describe("DefaultTemplateEditorPage", () => {
  beforeEach(() => {
    vi.mocked(offeringsApi.list).mockResolvedValue(offerings);
    vi.mocked(defaultTemplatesApi.get).mockResolvedValue(detail);
  });

  it("initializes URL type and auto-generates an offering-prefixed code until manually edited", async () => {
    const user = userEvent.setup();
    const router = createMemoryRouter(
      [{ path: "/platform/default-templates/new", element: <DefaultTemplateEditorPage /> }],
      { initialEntries: [`/platform/default-templates/new?offering_id=${coreHrId}&type=LETTER`] },
    );
    render(<RouterProvider router={router} />);

    const type = await screen.findByLabelText("Template type");
    expect(type).toHaveValue("LETTER");
    expect(screen.getByText("New draft")).toBeVisible();
    expect(screen.getByText("Not published")).toBeVisible();
    expect(screen.queryByText("All changes saved")).not.toBeInTheDocument();
    const name = screen.getByLabelText("Display name");
    const code = screen.getByLabelText("Template code");
    await user.type(name, "Offer Letter");
    expect(code).toHaveValue("core_hr_offer_letter");

    await user.selectOptions(screen.getByLabelText("Offering"), payrollId);
    expect(code).toHaveValue("future_payroll_offer_letter");
    await user.clear(code);
    await user.type(code, "custom_code");
    await user.clear(name);
    await user.type(name, "Revised Letter");
    expect(code).toHaveValue("custom_code");

    await user.click(screen.getByRole("button", { name: "Add placeholder" }));
    const placeholderKey = screen.getByLabelText("Key");
    await user.type(placeholderKey, "employee_name");
    expect(placeholderKey).toHaveValue("employee_name");
  }, 15_000);

  it("locks immutable edit identity and protects dirty navigation", async () => {
    const user = userEvent.setup();
    const router = createMemoryRouter([
      { path: "/platform/default-templates/:templateId", element: <DefaultTemplateEditorPage /> },
      { path: "/platform/default-templates", element: <h1>Catalog</h1> },
    ], { initialEntries: [`/platform/default-templates/${templateId}`] });
    render(<RouterProvider router={router} />);

    expect(await screen.findByRole("heading", { name: "Welcome Email" })).toBeVisible();
    expect(screen.getByLabelText("Template code")).toBeDisabled();
    expect(screen.getByLabelText("Key")).toBeDisabled();
    expect(screen.getByRole("checkbox", { name: "Required value" })).toBeDisabled();
    expect(screen.queryByRole("button", { name: "Add placeholder" })).not.toBeInTheDocument();
    expect(screen.getAllByRole("button", { name: "Publish changes" })).toHaveLength(2);

    await user.clear(screen.getByLabelText("Display name"));
    await user.type(screen.getByLabelText("Display name"), "Updated Welcome");
    const backLink = screen.getByRole("link", { name: "Default templates" });
    expect(backLink).toHaveAttribute(
      "href",
      `/platform/default-templates?offering_id=${coreHrId}&type=EMAIL`,
    );
    await user.click(backLink);
    expect(await screen.findByRole("dialog", { name: "Discard unsaved changes?" })).toBeVisible();
    expect(router.state.location.pathname).toBe(`/platform/default-templates/${templateId}`);
  });

  it("sends Ctrl+S through the versioned publish operation", async () => {
    const user = userEvent.setup();
    vi.mocked(defaultTemplatesApi.update).mockResolvedValue({ ...detail, name: "Updated Welcome", version: 4 });
    const router = createMemoryRouter(
      [{ path: "/platform/default-templates/:templateId", element: <DefaultTemplateEditorPage /> }],
      { initialEntries: [`/platform/default-templates/${templateId}`] },
    );
    render(<RouterProvider router={router} />);

    const name = await screen.findByLabelText("Display name");
    await user.clear(name);
    await user.type(name, "Updated Welcome");
    await user.keyboard("{Control>}s{/Control}");

    await waitFor(() => expect(defaultTemplatesApi.update).toHaveBeenCalledWith(templateId, {
      expected_version: 3,
      name: "Updated Welcome",
    }));
    expect(await screen.findByText("Default template updated.")).toBeVisible();
  });

  it("locks editor inputs while a publish request is in flight", async () => {
    const user = userEvent.setup();
    let resolveUpdate!: (value: DefaultTemplateDetail) => void;
    vi.mocked(defaultTemplatesApi.update).mockReturnValue(
      new Promise<DefaultTemplateDetail>((resolve) => {
        resolveUpdate = resolve;
      }),
    );
    const router = createMemoryRouter(
      [{ path: "/platform/default-templates/:templateId", element: <DefaultTemplateEditorPage /> }],
      { initialEntries: [`/platform/default-templates/${templateId}`] },
    );
    render(<RouterProvider router={router} />);

    const name = await screen.findByLabelText("Display name");
    await user.clear(name);
    await user.type(name, "Published Welcome");
    await user.click(screen.getAllByRole("button", { name: "Publish changes" })[0]);

    await waitFor(() => expect(defaultTemplatesApi.update).toHaveBeenCalled());
    expect(name).toBeDisabled();
    await user.type(name, " should not be lost");
    expect(name).toHaveValue("Published Welcome");

    resolveUpdate({ ...detail, name: "Published Welcome", version: 4 });
    expect(await screen.findByText("Default template updated.")).toBeVisible();
    expect(name).toHaveValue("Published Welcome");
  });

  it("treats a whitespace-only empty subject as a no-op", async () => {
    const user = userEvent.setup();
    vi.mocked(defaultTemplatesApi.get).mockResolvedValue({
      ...detail,
      subject: null,
      body: "Static body",
      placeholders: [],
    });
    const router = createMemoryRouter(
      [{ path: "/platform/default-templates/:templateId", element: <DefaultTemplateEditorPage /> }],
      { initialEntries: [`/platform/default-templates/${templateId}`] },
    );
    render(<RouterProvider router={router} />);

    const subject = await screen.findByLabelText(/Subject/);
    await user.type(subject, "   ");

    expect(screen.getAllByRole("button", { name: "Publish changes" })[0]).toBeDisabled();
    fireEvent.keyDown(document, { key: "s", ctrlKey: true });
    expect(defaultTemplatesApi.update).not.toHaveBeenCalled();
  });

  it("keeps offering and type context after creating a template", async () => {
    const user = userEvent.setup();
    vi.mocked(defaultTemplatesApi.create).mockResolvedValue({
      ...detail,
      type: "LETTER",
      code: "core_hr_offer_letter",
      name: "Offer Letter",
    });
    const router = createMemoryRouter([
      { path: "/platform/default-templates/new", element: <DefaultTemplateEditorPage /> },
      { path: "/platform/default-templates/:templateId", element: <h1>Created detail</h1> },
    ], { initialEntries: [`/platform/default-templates/new?offering_id=${coreHrId}&type=LETTER`] });
    const navigate = vi.spyOn(router, "navigate").mockResolvedValue();
    render(<RouterProvider router={router} />);

    await user.type(await screen.findByLabelText("Display name"), "Offer Letter");
    fireEvent.change(screen.getByLabelText(/Template body/), { target: { value: "Static offer body" } });
    await user.click(screen.getByRole("button", { name: "Add placeholder" }));
    await user.type(screen.getByLabelText("Key"), "candidate_name");
    await user.type(screen.getByLabelText("Label"), "Candidate name");
    await user.click(screen.getAllByRole("button", { name: "Create & publish" })[0]);

    await waitFor(() => expect(navigate).toHaveBeenCalledWith(
      `/platform/default-templates/${templateId}?offering_id=${coreHrId}&type=LETTER`,
      expect.objectContaining({ replace: true }),
    ));
    expect(defaultTemplatesApi.create).toHaveBeenCalledWith(expect.objectContaining({
      offering_id: coreHrId,
      type: "LETTER",
      placeholders: [{
        key: "candidate_name",
        label: "Candidate name",
        sample_value: "",
        required: false,
      }],
    }));
  });

  it("reloads the latest version after an optimistic concurrency conflict", async () => {
    const user = userEvent.setup();
    vi.mocked(defaultTemplatesApi.get)
      .mockResolvedValueOnce(detail)
      .mockResolvedValueOnce({ ...detail, name: "Server Welcome", version: 4 });
    vi.mocked(defaultTemplatesApi.update).mockRejectedValue(
      new ApiError("A newer version exists.", 409, null, "DEFAULT_TEMPLATE_STALE"),
    );
    const router = createMemoryRouter(
      [{ path: "/platform/default-templates/:templateId", element: <DefaultTemplateEditorPage /> }],
      { initialEntries: [`/platform/default-templates/${templateId}`] },
    );
    render(<RouterProvider router={router} />);

    const name = await screen.findByLabelText("Display name");
    await user.clear(name);
    await user.type(name, "Local Welcome");
    await user.click(screen.getAllByRole("button", { name: "Publish changes" })[0]);

    expect(await screen.findByText("Version conflict")).toBeVisible();
    await user.click(screen.getByRole("button", { name: "Reload and discard draft" }));
    await waitFor(() => expect(screen.getByLabelText("Display name")).toHaveValue("Server Welcome"));
    expect(defaultTemplatesApi.get).toHaveBeenCalledTimes(2);
    expect(screen.getByText("All changes saved")).toBeVisible();
  });

  it("previews the unsaved editor draft and its declared placeholders", async () => {
    const user = userEvent.setup();
    vi.mocked(defaultTemplatesApi.preview).mockResolvedValue({
      subject: "Welcome, Ada Lovelace",
      rendered_body: "**Updated**\n- Hello Ada Lovelace",
    });
    const router = createMemoryRouter(
      [{ path: "/platform/default-templates/:templateId", element: <DefaultTemplateEditorPage /> }],
      { initialEntries: [`/platform/default-templates/${templateId}`] },
    );
    render(<RouterProvider router={router} />);

    const body = await screen.findByLabelText(/Template body/);
    fireEvent.change(body, { target: { value: "Updated hello {{employee_name}}" } });
    await user.click(screen.getAllByRole("button", { name: "Preview draft" })[0]);

    await waitFor(() => expect(defaultTemplatesApi.preview).toHaveBeenCalledWith({
      subject: "Welcome, {{employee_name}}",
      body: "Updated hello {{employee_name}}",
      placeholders: detail.placeholders,
      sample_data: { employee_name: "Ada Lovelace" },
    }));
    expect(await screen.findByRole("dialog", { name: "Live Preview — Welcome Email" })).toBeVisible();
    expect(screen.getByText("Dynamic values are resolved; Markdown formatting is shown as source.")).toBeVisible();
    expect(screen.getByLabelText("Rendered Markdown source")).toHaveTextContent("**Updated**");
    const closePreview = screen.getByRole("button", { name: "Close template preview" });
    const done = screen.getByRole("button", { name: "Done" });
    expect(closePreview).toHaveFocus();
    fireEvent.keyDown(document, { key: "Tab", shiftKey: true });
    expect(done).toHaveFocus();
    fireEvent.keyDown(document, { key: "Tab" });
    expect(closePreview).toHaveFocus();
  });
});
