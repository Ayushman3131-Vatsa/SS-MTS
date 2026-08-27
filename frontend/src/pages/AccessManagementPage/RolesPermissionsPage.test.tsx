import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { RolesPermissionsPage } from "./RolesPermissionsPage";
import { SessionContext } from "../../entities/session/model/session-context";
import type { SessionContextValue } from "../../entities/session/model/session-context";
import type { PlatformPrincipal, TenantPrincipal } from "../../entities/session/model/session";
import {
  listPlatformRoles,
  listPlatformPages,
  listTenantRoles,
  listTenantPages,
  listTenantPageAccess,
} from "../../features/access-management/api/access-management-api";
import { defaultRolesApi } from "../../features/default-role-management/api/default-roles-api";
import { offeringsApi } from "../../features/offering-management/api/offerings-api";

vi.mock("../../features/access-management/api/access-management-api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../../features/access-management/api/access-management-api")>();
  return {
    ...actual,
    listPlatformRoles: vi.fn(),
    listPlatformPages: vi.fn(),
    listPlatformPageAccess: vi.fn().mockResolvedValue([]),
    listTenantRoles: vi.fn(),
    listTenantPages: vi.fn(),
    listTenantPageAccess: vi.fn(),
  };
});

vi.mock("../../features/default-role-management/api/default-roles-api", () => ({
  defaultRolesApi: {
    list: vi.fn(),
    get: vi.fn(),
    create: vi.fn(),
    update: vi.fn(),
    delete: vi.fn(),
  },
}));

vi.mock("../../features/offering-management/api/offerings-api", () => ({
  offeringsApi: {
    list: vi.fn(),
  },
}));

const platformPrincipal: PlatformPrincipal = {
  principal_type: "platform_admin",
  principal_id: "11111111-1111-4111-8111-111111111111",
  name: "Priya Operator",
  email: "priya@platform.example",
  role: "Platform Admin",
  tenant: null,
  password_change_required: false,
};

const tenantPrincipal: TenantPrincipal = {
  principal_type: "tenant_user",
  principal_id: "11111111-1111-4111-8111-111111111111",
  name: "Rahul Kumar",
  email: "rahul@infosys.example",
  role: "Tenant Admin",
  password_change_required: false,
  tenant: {
    tenant_id: "22222222-2222-4222-8222-222222222222",
    org_name: "Infosys",
    tenant_code: "INFY",
    status: "ACTIVE",
    offerings: [
      {
        offering_id: "33333333-3333-4333-8333-333333333333",
        code: "TASK_MANAGEMENT",
        display_name: "Task Management",
        description: "Plan work",
        icon_key: "clipboard-check",
        route_slug: "task-management",
        sort_order: 1,
      },
    ],
  },
};

const sessionValue = (principal: PlatformPrincipal | TenantPrincipal): SessionContextValue => ({
  status: "authenticated",
  principal,
  notice: null,
  clearNotice: vi.fn(),
  loginTenant: vi.fn(),
  loginPlatform: vi.fn(),
  changePassword: vi.fn(),
  logout: vi.fn(),
  retryBootstrap: vi.fn(),
});

const renderPlatform = (entry = "/platform/roles") =>
  render(
    <SessionContext.Provider value={sessionValue(platformPrincipal)}>
      <MemoryRouter initialEntries={[entry]}>
        <Routes>
          <Route path="/platform/roles" element={<RolesPermissionsPage realm="platform" />} />
        </Routes>
      </MemoryRouter>
    </SessionContext.Provider>,
  );

const renderTenant = () =>
  render(
    <SessionContext.Provider value={sessionValue(tenantPrincipal)}>
      <MemoryRouter initialEntries={["/t/INFY/app/roles"]}>
        <Routes>
          <Route path="/t/:tenantCode/app/roles" element={<RolesPermissionsPage realm="tenant" />} />
        </Routes>
      </MemoryRouter>
    </SessionContext.Provider>,
  );

describe("RolesPermissionsPage platform", () => {
  beforeEach(() => {
    vi.mocked(listPlatformRoles).mockResolvedValue([
      {
        role_id: "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
        role_code: "IT_ADMIN",
        role_name: "IT Administrator",
        description: null,
        is_system: false,
        is_active: true,
        module_scope: "platform",
        users_count: 4,
        created_at: "2026-08-01T00:00:00Z",
      },
    ]);
    vi.mocked(listPlatformPages).mockResolvedValue([]);
    vi.mocked(offeringsApi.list).mockResolvedValue([]);
    vi.mocked(defaultRolesApi.list).mockResolvedValue([
      {
        role_id: "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb",
        role_code: "TENANT_ADMIN",
        role_name: "Tenant Admin",
        description: "Workspace administrator",
        offering_id: null,
        offering_code: null,
        offering_name: null,
        module_scope: "CORE",
        is_system: true,
        is_active: true,
        page_count: 4,
        modify_count: 4,
        view_count: 0,
        none_count: 0,
        version: 1,
        created_at: "2026-08-01T00:00:00Z",
        updated_at: "2026-08-01T00:00:00Z",
      },
    ]);
    vi.mocked(defaultRolesApi.get).mockResolvedValue({
      role_id: "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb",
      role_code: "TENANT_ADMIN",
      role_name: "Tenant Admin",
      description: "Workspace administrator",
      offering_id: null,
      offering_code: null,
      offering_name: null,
      module_scope: "CORE",
      is_system: true,
      is_active: true,
      page_count: 4,
      modify_count: 4,
      view_count: 0,
      none_count: 0,
      version: 1,
      created_at: "2026-08-01T00:00:00Z",
      updated_at: "2026-08-01T00:00:00Z",
      page_access: [],
    });
  });

  it("switches from platform roles to tenant defaults with the catalog control", async () => {
    renderPlatform();
    expect(await screen.findByRole("heading", { name: "IT Administrator" })).toBeVisible();
    await userEvent.click(screen.getByRole("radio", { name: "Tenant" }));
    expect(await screen.findByRole("heading", { name: "Tenant Admin" })).toBeVisible();
    expect(screen.getByLabelText("Offering")).toBeVisible();
    expect(defaultRolesApi.list).toHaveBeenCalled();
  });
});

describe("RolesPermissionsPage tenant", () => {
  beforeEach(() => {
    vi.mocked(listTenantRoles).mockResolvedValue([
      {
        role_id: "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb",
        role_code: "TENANT_ADMIN",
        role_name: "Tenant Admin",
        description: null,
        is_system: true,
        is_active: true,
        module_scope: "CORE",
        users_count: 1,
        created_at: "2026-08-01T00:00:00Z",
      },
      {
        role_id: "cccccccc-cccc-4ccc-8ccc-cccccccccccc",
        role_code: "TASK_ADMIN",
        role_name: "Task Administrator",
        description: null,
        is_system: false,
        is_active: true,
        module_scope: "TASK_MANAGEMENT",
        users_count: 2,
        created_at: "2026-08-01T00:00:00Z",
      },
    ]);
    vi.mocked(listTenantPages).mockResolvedValue([
      {
        page_id: "dddddddd-dddd-4ddd-8ddd-dddddddddddd",
        page_code: "TENANT_TASKS",
        module: "task_management",
        page_name: "All Tasks",
        route: "/tasks",
        app_scope: "tenant",
        offering_code: "TASK_MANAGEMENT",
      },
      {
        page_id: "eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee",
        page_code: "TENANT_MY_WORK",
        module: "task_management",
        page_name: "My Work",
        route: "/my-work",
        app_scope: "tenant",
        offering_code: "TASK_MANAGEMENT",
      },
    ]);
    vi.mocked(listTenantPageAccess).mockResolvedValue([
      {
        page: {
          page_id: "dddddddd-dddd-4ddd-8ddd-dddddddddddd",
          page_code: "TENANT_TASKS",
          module: "task_management",
          page_name: "All Tasks",
          route: "/tasks",
          app_scope: "tenant",
          offering_code: "TASK_MANAGEMENT",
        },
        access_level: "modify",
      },
    ]);
  });

  it("hides platform catalog controls and lists Task Management when creating a role", async () => {
    renderTenant();
    expect(await screen.findByRole("heading", { name: "Tenant Admin" })).toBeVisible();
    expect(screen.getByLabelText("Offering")).toBeVisible();
    expect(screen.queryByRole("heading", { name: "Task Administrator" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Platform" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Tenant defaults" })).not.toBeInTheDocument();
    expect(screen.queryByRole("radio", { name: "Platform" })).not.toBeInTheDocument();

    await userEvent.selectOptions(screen.getByLabelText("Offering"), "33333333-3333-4333-8333-333333333333");
    expect(await screen.findByRole("heading", { name: "Task Administrator" })).toBeVisible();
    expect(screen.queryByRole("heading", { name: "Tenant Admin" })).not.toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: "New role" }));
    const dialog = screen.getByRole("dialog", { name: "New role" });
    expect(screen.queryByRole("radio", { name: "Platform" })).not.toBeInTheDocument();
    expect(within(dialog).getByLabelText("Module")).toBeVisible();
    expect(within(dialog).getByRole("option", { name: "Task Management" })).toBeInTheDocument();
    expect(within(dialog).queryByText(/· \d+ pages/)).not.toBeInTheDocument();
  });
});
