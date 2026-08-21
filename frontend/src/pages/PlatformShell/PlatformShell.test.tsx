import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import { SessionContext } from "../../entities/session/model/session-context";
import type { SessionContextValue } from "../../entities/session/model/session-context";
import type { PlatformPrincipal } from "../../entities/session/model/session";
import { PlatformShell } from "./PlatformShell";

const principal: PlatformPrincipal = {
  principal_type: "platform_admin",
  principal_id: "11111111-1111-4111-8111-111111111111",
  name: "Priya Operator",
  email: "priya@platform.example",
  role: "Platform Admin",
  tenant: null,
  password_change_required: false,
};

const renderShell = () => {
  const context: SessionContextValue = {
    status: "authenticated",
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
        initialEntries={["/platform"]}
        future={{ v7_relativeSplatPath: true, v7_startTransition: true }}
      >
        <Routes>
          <Route path="/platform" element={<PlatformShell />}>
            <Route index element={<h1>Dashboard content</h1>} />
            <Route path="tenants" element={<h1>Tenant content</h1>} />
            <Route path="tenants/register" element={<h1>Register content</h1>} />
            <Route path="offerings" element={<h1>Offering content</h1>} />
            <Route path="default-templates" element={<h1>Default templates content</h1>} />
          </Route>
        </Routes>
      </MemoryRouter>
    </SessionContext.Provider>,
  );

  return context;
};

describe("PlatformShell", () => {
  it("renders platform navigation and marks the active route", () => {
    renderShell();

    const navigation = screen.getByRole("navigation", {
      name: "Platform navigation",
    });
    const links = navigation.querySelectorAll("a");
    expect(links).toHaveLength(5);
    expect(screen.getByRole("link", { name: "Dashboard" })).toHaveAttribute(
      "aria-current",
      "page",
    );

    fireEvent.click(screen.getByRole("link", { name: "All Tenants" }));
    expect(screen.getByRole("heading", { name: "Tenant content" })).toBeVisible();
    expect(screen.getByRole("link", { name: "Default Templates" })).toHaveAttribute(
      "href",
      "/platform/default-templates",
    );
  });

  it("closes the mobile drawer with Escape and restores focus", () => {
    renderShell();
    const menu = document.querySelector<HTMLButtonElement>(
      "button[aria-label='Open platform navigation']",
    );
    expect(menu).not.toBeNull();
    if (!menu) {
      return;
    }

    menu.focus();
    fireEvent.click(menu);
    expect(menu).toHaveAttribute("aria-expanded", "true");
    fireEvent.keyDown(document, { key: "Escape" });

    expect(menu).toHaveAttribute("aria-expanded", "false");
    expect(menu).toHaveFocus();
  });

  it("uses the existing secure logout operation", () => {
    const context = renderShell();

    fireEvent.click(screen.getByRole("button", { name: "Sign out" }));

    expect(context.logout).toHaveBeenCalledOnce();
  });
});
