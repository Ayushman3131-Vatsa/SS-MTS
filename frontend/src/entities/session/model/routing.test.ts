import { describe, expect, it } from "vitest";

import { getPrincipalHome } from "./routing";
import type { SessionPrincipal } from "./session";

const tenantPrincipal = (
  role: string,
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

describe("getPrincipalHome", () => {
  it.each(["Tenant Admin", "Task Manager"] as const)(
    "routes %s to the tenant overview",
    (role) => {
      expect(getPrincipalHome(tenantPrincipal(role))).toBe("/app/overview");
    },
  );

  it("routes every suspended tenant user to the restricted status page", () => {
    expect(getPrincipalHome(tenantPrincipal("Tenant Admin", "SUSPENDED"))).toBe(
      "/app/suspended",
    );
  });

  it("routes platform administrators to the platform console", () => {
    expect(
      getPrincipalHome({
        principal_type: "platform_admin",
        principal_id: "d94f8e58-05d0-4df1-868b-69a843c5d3a7",
        name: "Platform Operator",
        email: "operator@example.com",
        role: "Platform Admin",
        tenant: null,
        password_change_required: false,
      }),
    ).toBe("/platform");
  });

  it("routes a first-login platform administrator to change password", () => {
    expect(
      getPrincipalHome({
        principal_type: "platform_admin",
        principal_id: "d94f8e58-05d0-4df1-868b-69a843c5d3a7",
        name: "Platform Operator",
        email: "operator@example.com",
        role: "Platform Admin",
        tenant: null,
        password_change_required: true,
      }),
    ).toBe("/account/change-password");
  });
});
