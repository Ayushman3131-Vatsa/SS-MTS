import { act, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { SessionPrincipal } from "../../entities/session/model/session";
import { useSession } from "../../entities/session/model/session-context";
import { sessionApi } from "../../features/auth/api/session-api";
import { SESSION_EXPIRED_EVENT } from "../../shared/api/session-events";
import { AuthProvider } from "./AuthProvider";

const principal: SessionPrincipal = {
  principal_type: "tenant_user",
  principal_id: "d94f8e58-05d0-4df1-868b-69a843c5d3a7",
  name: "Avery Morgan",
  email: "avery@example.com",
  role: "Tenant Admin",
  tenant: {
    tenant_id: "63e6c159-3c6c-43bb-856a-8ed53e21dabe",
    org_name: "Northstar Labs",
    workspace_slug: "northstar-labs",
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
});
