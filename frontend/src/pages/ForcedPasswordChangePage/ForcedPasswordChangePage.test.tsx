import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import {
  SessionContext,
  type SessionContextValue,
} from "../../entities/session/model/session-context";
import type { TenantPrincipal } from "../../entities/session/model/session";
import { ForcedPasswordChangePage } from "./ForcedPasswordChangePage";

const pendingPrincipal: TenantPrincipal = {
  principal_type: "tenant_user",
  principal_id: "d94f8e58-05d0-4df1-868b-69a843c5d3a7",
  name: "Avery Morgan",
  email: "avery@example.com",
  role: "Tenant Admin",
  password_change_required: true,
  tenant: {
    tenant_id: "63e6c159-3c6c-43bb-856a-8ed53e21dabe",
    org_name: "Northstar Labs",
    tenant_code: "NORTHSTAR",
    status: "ACTIVE",
    offerings: [],
  },
};

describe("ForcedPasswordChangePage", () => {
  it("changes the password and keeps the current browser signed in", async () => {
    const user = userEvent.setup();
    const updatedPrincipal = {
      ...pendingPrincipal,
      password_change_required: false as const,
    };
    const changePassword = vi.fn().mockResolvedValue(updatedPrincipal);
    const context: SessionContextValue = {
      status: "authenticated",
      principal: pendingPrincipal,
      notice: null,
      clearNotice: vi.fn(),
      loginTenant: vi.fn(),
      loginPlatform: vi.fn(),
      changePassword,
      logout: vi.fn(),
      retryBootstrap: vi.fn(),
    };

    render(
      <SessionContext.Provider value={context}>
        <MemoryRouter
          initialEntries={["/account/change-password"]}
          future={{ v7_relativeSplatPath: true, v7_startTransition: true }}
        >
          <Routes>
            <Route path="/account/change-password" element={<ForcedPasswordChangePage />} />
            <Route path="/app/overview" element={<h1>Tenant home</h1>} />
          </Routes>
        </MemoryRouter>
      </SessionContext.Provider>,
    );

    await user.type(screen.getByLabelText("Temporary password"), "Temporary!Password42");
    await user.type(screen.getByLabelText("New password"), "Permanent!Password84");
    await user.type(screen.getByLabelText("Confirm new password"), "Permanent!Password84");
    await user.click(screen.getByRole("button", { name: "Save password and continue" }));

    expect(changePassword).toHaveBeenCalledWith({
      current_password: "Temporary!Password42",
      new_password: "Permanent!Password84",
    });
    expect(await screen.findByRole("heading", { name: "Tenant home" })).toBeVisible();
  });
});
