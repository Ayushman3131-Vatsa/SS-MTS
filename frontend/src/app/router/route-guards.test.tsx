import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import { SessionContext } from "../../entities/session/model/session-context";
import type {
  SessionContextValue,
} from "../../entities/session/model/session-context";
import type {
  SessionPrincipal,
  TenantRole,
} from "../../entities/session/model/session";
import { OfferingRoute, ProtectedRoute } from "./route-guards";

const tenantPrincipal = (
  role: TenantRole,
  status: "ACTIVE" | "SUSPENDED" = "ACTIVE",
): SessionPrincipal => ({
  principal_type: "tenant_user",
  principal_id: "d94f8e58-05d0-4df1-868b-69a843c5d3a7",
  name: "Avery Morgan",
  email: "avery@example.com",
  role,
  password_change_required: false,
  tenant: {
    tenant_id: "63e6c159-3c6c-43bb-856a-8ed53e21dabe",
    org_name: "Northstar Labs",
    tenant_code: "NORTHSTAR",
    status,
    offerings: [],
  },
});

const platformPrincipal: SessionPrincipal = {
  principal_type: "platform_admin",
  principal_id: "764a30d1-f70e-484c-89dc-e45b99dda178",
  name: "Platform Operator",
  email: "operator@example.com",
  role: "Platform Admin",
  tenant: null,
  password_change_required: false,
};

const renderProtectedRoute = (
  principal: SessionPrincipal | null,
  guard: React.ReactNode,
) => {
  const context: SessionContextValue = {
    status: principal ? "authenticated" : "unauthenticated",
    principal,
    notice: null,
    clearNotice: vi.fn(),
    loginTenant: vi.fn(),
    loginPlatform: vi.fn(),
    changePassword: vi.fn(),
    logout: vi.fn(),
    retryBootstrap: vi.fn(),
  };

  render(
    <SessionContext.Provider value={context}>
      <MemoryRouter
        initialEntries={["/protected"]}
        future={{ v7_relativeSplatPath: true, v7_startTransition: true }}
      >
        <Routes>
          <Route element={guard}>
            <Route path="/protected" element={<div>Protected content</div>} />
          </Route>
          <Route path="/login" element={<div>Login screen</div>} />
          <Route path="/forbidden" element={<div>Forbidden screen</div>} />
          <Route path="/app/suspended" element={<div>Suspended screen</div>} />
          <Route path="/app/my-work" element={<div>Tenant home</div>} />
        </Routes>
      </MemoryRouter>
    </SessionContext.Provider>,
  );
};

describe("ProtectedRoute", () => {
  it("redirects an unauthenticated visitor to login", () => {
    renderProtectedRoute(null, <ProtectedRoute />);
    expect(screen.getByText("Login screen")).toBeVisible();
  });

  it("allows the requested tenant roles", () => {
    renderProtectedRoute(
      tenantPrincipal("Project Manager"),
      <ProtectedRoute
        area="tenant"
        roles={["Tenant Admin", "Project Manager"]}
      />,
    );
    expect(screen.getByText("Protected content")).toBeVisible();
  });

  it("redirects a suspended tenant away from every feature route", () => {
    renderProtectedRoute(
      tenantPrincipal("Tenant Admin", "SUSPENDED"),
      <ProtectedRoute area="tenant" />,
    );
    expect(screen.getByText("Suspended screen")).toBeVisible();
    expect(screen.queryByText("Protected content")).not.toBeInTheDocument();
  });

  it("allows a suspended tenant into the dedicated suspension route", () => {
    renderProtectedRoute(
      tenantPrincipal("Tenant Admin", "SUSPENDED"),
      <ProtectedRoute area="tenant" allowSuspendedTenant />,
    );
    expect(screen.getByText("Protected content")).toBeVisible();
  });

  it("blocks a tenant role from another tenant role area", () => {
    renderProtectedRoute(
      tenantPrincipal("Employee"),
      <ProtectedRoute
        area="tenant"
        roles={["Tenant Admin", "Project Manager"]}
      />,
    );
    expect(screen.getByText("Forbidden screen")).toBeVisible();
  });

  it("blocks platform principals from tenant routes", () => {
    renderProtectedRoute(
      platformPrincipal,
      <ProtectedRoute area="tenant" />,
    );
    expect(screen.getByText("Forbidden screen")).toBeVisible();
  });

  it("allows platform principals into the platform area", () => {
    renderProtectedRoute(
      platformPrincipal,
      <ProtectedRoute area="platform" />,
    );
    expect(screen.getByText("Protected content")).toBeVisible();
  });
});

describe("OfferingRoute", () => {
  it("allows a tenant with the effective offering", () => {
    const principal = tenantPrincipal("Employee");
    if (principal.principal_type === "tenant_user") {
      principal.tenant.offerings = [{
        offering_id: "11111111-1111-4111-8111-111111111111",
        code: "TASK_MANAGEMENT",
        display_name: "Task Management",
        description: "Plan work",
        icon_key: "clipboard-check",
        route_slug: "task-management",
        sort_order: 1,
      }];
    }
    renderProtectedRoute(principal, <OfferingRoute code="TASK_MANAGEMENT" />);
    expect(screen.getByText("Protected content")).toBeVisible();
  });

  it("redirects a direct URL when the offering is missing", () => {
    renderProtectedRoute(tenantPrincipal("Employee"), <OfferingRoute code="TASK_MANAGEMENT" />);
    expect(screen.queryByText("Protected content")).not.toBeInTheDocument();
  });
});
