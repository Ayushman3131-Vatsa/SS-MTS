import { act, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { SessionPrincipal } from "../../entities/session/model/session";
import { useSession } from "../../entities/session/model/session-context";
import { sessionApi } from "../../features/auth/api/session-api";
import {
  SESSION_EXPIRED_EVENT,
  TENANT_ACCESS_CHANGED_EVENT,
} from "../../shared/api/session-events";
import { AuthProvider } from "./AuthProvider";

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
    status: "ACTIVE",
    offerings: [],
  },
};

const SessionProbe = () => {
  const { notice, principal: currentPrincipal, status } = useSession();
  return (
    <div>
      <span>{status}</span>
      <span>{currentPrincipal?.email || "no principal"}</span>
      <span>{notice || "no notice"}</span>
      <span>
        {currentPrincipal?.principal_type === "tenant_user"
          ? currentPrincipal.tenant.status
          : "no tenant status"}
      </span>
    </div>
  );
};

describe("AuthProvider", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("restores an existing browser session during bootstrap", async () => {
    vi.spyOn(sessionApi, "restore").mockResolvedValue(principal);

    render(
      <AuthProvider>
        <SessionProbe />
      </AuthProvider>,
    );

    expect(await screen.findByText("authenticated")).toBeVisible();
    expect(screen.getByText("avery@example.com")).toBeVisible();
  });

  it("clears local identity when a protected request reports expiry", async () => {
    vi.spyOn(sessionApi, "restore").mockResolvedValue(principal);

    render(
      <AuthProvider>
        <SessionProbe />
      </AuthProvider>,
    );
    await screen.findByText("authenticated");

    act(() => {
      window.dispatchEvent(new Event(SESSION_EXPIRED_EVENT));
    });

    await waitFor(() =>
      expect(screen.getByText("unauthenticated")).toBeVisible(),
    );
    expect(screen.getByText("no principal")).toBeVisible();
    expect(screen.getByText(/session has expired/i)).toBeVisible();
  });

  it("keeps a suspended tenant authenticated after an access change", async () => {
    let restoreCalls = 0;
    vi.spyOn(sessionApi, "restore").mockImplementation(async () => {
      restoreCalls += 1;
      if (restoreCalls === 1) return principal;
      return {
        ...principal,
        tenant: { ...principal.tenant, status: "SUSPENDED" },
      };
    });

    render(
      <AuthProvider>
        <SessionProbe />
      </AuthProvider>,
    );
    await screen.findByText("authenticated");

    act(() => {
      window.dispatchEvent(
        new CustomEvent(TENANT_ACCESS_CHANGED_EVENT, {
          detail: { code: "TENANT_SUSPENDED" },
        }),
      );
    });

    await waitFor(() => expect(screen.getByText("SUSPENDED")).toBeVisible());
    expect(screen.getByText("authenticated")).toBeVisible();
    expect(screen.getByText("avery@example.com")).toBeVisible();
  });

  it("automatically restores workspace access after platform reactivation", async () => {
    let restoreCalls = 0;
    vi.spyOn(sessionApi, "restore").mockImplementation(async () => {
      restoreCalls += 1;
      return restoreCalls === 1
        ? { ...principal, tenant: { ...principal.tenant, status: "SUSPENDED" } }
        : principal;
    });

    render(
      <AuthProvider>
        <SessionProbe />
      </AuthProvider>,
    );
    await screen.findByText("SUSPENDED");

    act(() => window.dispatchEvent(new Event("focus")));

    await waitFor(() => expect(screen.getByText("ACTIVE")).toBeVisible());
    expect(screen.getByText("authenticated")).toBeVisible();
  });
});
