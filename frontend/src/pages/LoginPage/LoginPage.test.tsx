import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import { LoginPage } from "./LoginPage";
import { sessionApi } from "../../features/auth/api/session-api";
import { SessionContext, type SessionContextValue } from "../../entities/session/model/session-context";

const mockSessionContext: SessionContextValue = {
  status: "unauthenticated",
  principal: null,
  notice: null,
  clearNotice: vi.fn(),
  loginTenant: vi.fn(),
  loginPlatform: vi.fn(),
  changePassword: vi.fn(),
  logout: vi.fn(),
  retryBootstrap: vi.fn(),
};

const renderPage = (initialEntry: string) => {
  render(
    <SessionContext.Provider value={mockSessionContext}>
      <MemoryRouter initialEntries={[initialEntry]}>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route path="/:tenantCode/login" element={<LoginPage />} />
        </Routes>
      </MemoryRouter>
    </SessionContext.Provider>,
  );
};

describe("LoginPage tenant verification", () => {
  it("displays organization name when tenant is valid", async () => {
    vi.spyOn(sessionApi, "lookupTenant").mockResolvedValue({
      exists: true,
      tenant_code: "NET",
      org_name: "Netflix",
    });

    renderPage("/NET/login");

    expect(await screen.findByRole("heading", { name: "Sign in to Netflix" })).toBeVisible();
    expect(screen.queryByLabelText("Tenant code")).not.toBeInTheDocument();
  });

  it("displays error alert and editable Tenant code field when tenant code is invalid", async () => {
    vi.spyOn(sessionApi, "lookupTenant").mockResolvedValue({
      exists: false,
      tenant_code: "NET123",
      org_name: null,
    });

    renderPage("/NET123/login");

    expect(await screen.findByRole("heading", { name: "Tenant not found" })).toBeVisible();
    expect(
      screen.getByText(/Tenant "NET123" does not exist. Please check the URL or enter your tenant code below./i),
    ).toBeVisible();
    expect(screen.getByLabelText("Tenant code")).toBeInTheDocument();
  });

  it("displays Welcome back and editable Tenant code field on generic /login", () => {
    renderPage("/login");

    expect(screen.getByRole("heading", { name: "Welcome back" })).toBeVisible();
    expect(screen.getByLabelText("Tenant code")).toBeInTheDocument();
  });
});
