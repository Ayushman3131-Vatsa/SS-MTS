import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import { SessionContext } from "../../entities/session/model/session-context";
import type { SessionContextValue } from "../../entities/session/model/session-context";
import type { SessionPrincipal } from "../../entities/session/model/session";
import { SuspendedTenantPage } from "./SuspendedTenantPage";

const principal: SessionPrincipal = {
  principal_type: "tenant_user",
  principal_id: "d94f8e58-05d0-4df1-868b-69a843c5d3a7",
  name: "Avery Morgan",
  email: "avery@example.com",
  role: "Tenant Admin",
  password_change_required: false,
  tenant: {
    tenant_id: "63e6c159-3c6c-43bb-856a-8ed53e21dabe",
    org_name: "Northstar Labs",
    tenant_code: "NORTHSTAR",
    status: "SUSPENDED",
    offerings: [],
  },
};

describe("SuspendedTenantPage", () => {
  it("shows a restricted session with sign out as the only action", () => {
    const logout = vi.fn().mockResolvedValue(undefined);
    const context: SessionContextValue = {
      status: "authenticated",
      principal,
      notice: null,
      clearNotice: vi.fn(),
      loginTenant: vi.fn(),
      loginPlatform: vi.fn(),
      changePassword: vi.fn(),
      logout,
      retryBootstrap: vi.fn(),
    };

    render(
      <SessionContext.Provider value={context}>
        <MemoryRouter future={{ v7_relativeSplatPath: true, v7_startTransition: true }}>
          <SuspendedTenantPage />
        </MemoryRouter>
      </SessionContext.Provider>,
    );

    expect(screen.getByRole("heading", { name: /temporarily suspended/i })).toBeVisible();
    expect(screen.getByText(/signed in successfully/i)).toBeVisible();
    expect(screen.getByText("NORTHSTAR")).toBeVisible();
    expect(screen.getAllByRole("button")).toHaveLength(1);

    fireEvent.click(screen.getByRole("button", { name: "Sign out" }));
    expect(logout).toHaveBeenCalledOnce();
  });
});
