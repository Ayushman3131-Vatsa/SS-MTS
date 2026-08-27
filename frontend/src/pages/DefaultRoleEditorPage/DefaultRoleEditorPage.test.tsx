import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { RouterProvider, createMemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { defaultRolesApi } from "../../features/default-role-management/api/default-roles-api";
import { offeringsApi } from "../../features/offering-management/api/offerings-api";
import { DefaultRoleEditorPage } from "./DefaultRoleEditorPage";

vi.mock("../../features/default-role-management/api/default-roles-api", () => ({
  defaultRolesApi: {
    pages: vi.fn(),
    create: vi.fn(),
    get: vi.fn(),
    update: vi.fn(),
    delete: vi.fn(),
  },
}));

vi.mock("../../features/offering-management/api/offerings-api", () => ({
  offeringsApi: {
    list: vi.fn(),
  },
}));

const page = {
  page_id: "55555555-5555-4555-8555-555555555555",
  page_code: "TENANT_USERS",
  module: "workspace",
  page_name: "Users",
  route: "/app/users",
  app_scope: "tenant",
  offering_code: null,
};

describe("DefaultRoleEditorPage", () => {
  beforeEach(() => {
    vi.mocked(offeringsApi.list).mockResolvedValue([]);
    vi.mocked(defaultRolesApi.pages).mockResolvedValue({
      module_scope: "CORE",
      offering_id: null,
      offering_code: null,
      offering_name: null,
      pages: [page],
    });
  });

  it("creates a workspace role with page access", async () => {
    vi.mocked(defaultRolesApi.create).mockResolvedValue({
      role_id: "44444444-4444-4444-8444-444444444444",
      role_code: "HR_ADMIN",
      role_name: "HR Admin",
      description: null,
      offering_id: null,
      offering_code: null,
      offering_name: null,
      module_scope: "CORE",
      is_system: false,
      is_active: true,
      page_count: 1,
      modify_count: 1,
      view_count: 0,
      none_count: 0,
      version: 1,
      created_at: "2026-08-06T00:00:00Z",
      updated_at: "2026-08-06T00:00:00Z",
      page_access: [{ page, access_level: "modify" }],
    });

    const router = createMemoryRouter(
      [
        { path: "/platform/default-roles/new", element: <DefaultRoleEditorPage /> },
        { path: "/platform/default-roles/:roleId", element: <div>Saved</div> },
      ],
      { initialEntries: ["/platform/default-roles/new?scope=CORE"] },
    );
    render(<RouterProvider router={router} />);

    expect(await screen.findByText("Users")).toBeVisible();
    await userEvent.type(screen.getByLabelText("Role name"), "HR Admin");
    await userEvent.click(screen.getByRole("button", { name: "Modify" }));
    await userEvent.click(screen.getByRole("button", { name: "Save" }));

    await waitFor(() => expect(defaultRolesApi.create).toHaveBeenCalledTimes(1));
    expect(defaultRolesApi.create).toHaveBeenCalledWith(
      expect.objectContaining({
        role_name: "HR Admin",
        offering_id: null,
        entries: [{ page_id: page.page_id, access_level: "modify" }],
      }),
    );
  });
});
