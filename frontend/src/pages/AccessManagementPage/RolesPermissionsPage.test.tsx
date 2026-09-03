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
      <MemoryRouter initialEntries={["/INFY/app/roles"]}>
        <Routes>
          <Route path="/:tenantCode/app/roles" element={<RolesPermissionsPage realm="tenant" />} />
        </Routes>
      </MemoryRouter>
    </SessionContext.Provider>,
  );

// Helper: the roles table lists role names as plain text (not headings), each row has
// its own "View" button. Click the row's View button to open the permission studio.
const openRoleFromTable = async (roleName: string) => {
  const nameCell = await screen.findByText(roleName);
  const row = nameCell.closest("tr");
  if (!row) throw new Error(`Could not find table row for role "${roleName}"`);
  await userEvent.click(within(row).getByRole("button", { name: "View / Edit" }));
};

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

  it("switches from platform roles to tenant defaults with the catalog control, and View opens the permission studio", async () => {
    renderPlatform();

    // Roles table is the landing screen.
    expect(await screen.findByRole("heading", { name: "Roles" })).toBeVisible();
    await openRoleFromTable("IT Administrator");
    expect(await screen.findByRole("heading", { name: "IT Administrator" })).toBeVisible();

    // Back to the table, then switch to tenant defaults.
    await userEvent.click(screen.getByRole("button", { name: "Back to roles" }));
    await userEvent.selectOptions(screen.getByLabelText("Role type"), "tenant");
    expect(screen.getByLabelText("Offering")).toBeVisible();
    expect(defaultRolesApi.list).toHaveBeenCalled();

    await openRoleFromTable("Tenant Admin");
    expect(await screen.findByRole("heading", { name: "Tenant Admin" })).toBeVisible();
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

  it("hides platform catalog controls, filters by offering in the table, and lets you view/edit permissions", async () => {
    renderTenant();

    // Roles table is the landing screen, displaying All Offerings by default.
    expect(await screen.findByText("Tenant Admin")).toBeVisible();
    expect(screen.getByLabelText("Offering")).toBeVisible();
    expect(await screen.findByText("Task Administrator")).toBeVisible();
    expect(screen.queryByLabelText("Role type")).not.toBeInTheDocument();

    // Switch the table to the Task Management offering.
    await userEvent.selectOptions(screen.getByLabelText("Offering"), "Task Management");
    expect(await screen.findByText("Task Administrator")).toBeVisible();
    expect(screen.queryByText("Tenant Admin")).not.toBeInTheDocument();

    // Open the role and confirm its permission grid is editable (View button navigated
    // into the studio; "Save changes" is enabled only once an access level changes).
    await openRoleFromTable("Task Administrator");
    expect(await screen.findByRole("heading", { name: "Task Administrator" })).toBeVisible();
    expect(screen.getByText("All Tasks")).toBeVisible();
    const saveButton = screen.getByRole("button", { name: "Save changes" });
    expect(saveButton).toBeDisabled();
    const accessGroup = screen.getByRole("group", { name: "All Tasks access" });
    await userEvent.click(within(accessGroup).getByRole("button", { name: "None" }));
    expect(saveButton).toBeEnabled();

    // Creating a new role still hides the Platform choice and scopes modules to what's licensed.
    await userEvent.click(screen.getByRole("button", { name: "Back to roles" }));
    await userEvent.click(screen.getByRole("button", { name: "Create Role" }));
    const dialog = screen.getByRole("dialog", { name: "New role" });
    expect(screen.queryByRole("radio", { name: "Platform" })).not.toBeInTheDocument();
    expect(within(dialog).getByLabelText("Offering")).toBeVisible();
    expect(within(dialog).getByRole("option", { name: "Task Management" })).toBeInTheDocument();
  });
});