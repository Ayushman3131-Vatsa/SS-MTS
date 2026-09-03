import { fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { MemoryRouter, Route, Routes } from "react-router-dom";

import { SessionContext, type SessionContextValue } from "../../entities/session/model/session-context";
import type { TenantPrincipal } from "../../entities/session/model/session";
import { TenantShell } from "./TenantShell";

const principal = (enabled: boolean): TenantPrincipal => ({
  principal_type: "tenant_user",
  principal_id: "11111111-1111-4111-8111-111111111111",
  name: "Avery Morgan",
  email: "avery@example.com",
  role: "Tenant Admin",
  password_change_required: false,
  tenant: {
    tenant_id: "22222222-2222-4222-8222-222222222222",
    org_name: "Northstar Labs",
    tenant_code: "NORTHSTAR",
    status: "ACTIVE",
    offerings: enabled ? [{
      offering_id: "33333333-3333-4333-8333-333333333333",
      code: "TASK_MANAGEMENT",
      display_name: "Task Management",
      description: "Plan work",
      icon_key: "clipboard-check",
      route_slug: "task-management",
      sort_order: 1,
    }] : [],
  },
});

const renderShell = (enabled: boolean, path = "/NORTHSTAR/app/overview") => {
  const context: SessionContextValue = { status: "authenticated", principal: principal(enabled), notice: null, clearNotice: vi.fn(), loginTenant: vi.fn(), loginPlatform: vi.fn(), changePassword: vi.fn(), logout: vi.fn(), retryBootstrap: vi.fn() };
  render(<SessionContext.Provider value={context}><MemoryRouter initialEntries={[path]} future={{ v7_relativeSplatPath: true, v7_startTransition: true }}><Routes><Route path="/:tenantCode/app" element={<TenantShell />}><Route path="overview" element={<div>Tenant home</div>} /><Route path="task-management/*" element={<div>Task workspace</div>} /></Route></Routes></MemoryRouter></SessionContext.Provider>);
};

describe("TenantShell task navigation", () => {
  beforeEach(() => window.localStorage.clear());

  it("does not render Task Management without an effective offering", () => {
    renderShell(false);
    expect(screen.queryByRole("button", { name: "Task Management" })).not.toBeInTheDocument();
  });

  it("expands with keyboard, persists the tenant state and is never draggable", async () => {
    const user = userEvent.setup();
    renderShell(true);
    const group = screen.getByRole("button", { name: "Task Management" });
    expect(group).toHaveAttribute("aria-expanded", "false");
    expect(group).not.toHaveAttribute("draggable", "true");
    group.focus();
    await user.keyboard("{Enter}");
    expect(group).toHaveAttribute("aria-expanded", "true");
    expect(screen.getByRole("link", { name: "All Tasks" })).toHaveAttribute("href", "/NORTHSTAR/app/task-management/tasks");
    expect(window.localStorage.getItem("task-management-navigation:22222222-2222-4222-8222-222222222222")).toBe("expanded");
  });

  it("automatically expands on Task Management routes", () => {
    renderShell(true, "/NORTHSTAR/app/task-management/projects");
    expect(screen.getByRole("button", { name: "Task Management" })).toHaveAttribute("aria-expanded", "true");
    fireEvent.click(screen.getByRole("button", { name: "Task Management" }));
    expect(screen.getByRole("button", { name: "Task Management" })).toHaveAttribute("aria-expanded", "false");
  });

  it("groups users and roles under User Access Management", () => {
    renderShell(false);
    fireEvent.click(screen.getByRole("button", { name: "User Access Management" }));
    expect(screen.getByRole("link", { name: "Users" })).toHaveAttribute("href", "/NORTHSTAR/app/users");
    expect(screen.getByRole("link", { name: "Roles & permissions" })).toHaveAttribute("href", "/NORTHSTAR/app/roles");
    expect(screen.queryByRole("link", { name: "Permissions" })).not.toBeInTheDocument();
  });
});

