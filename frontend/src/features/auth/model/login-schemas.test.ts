import { describe, expect, it } from "vitest";

import { platformLoginSchema, tenantLoginSchema } from "./login-schemas";

describe("tenantLoginSchema", () => {
  it("accepts a valid login without applying account-creation password rules", () => {
    const result = tenantLoginSchema.safeParse({
      workspaceSlug: "northstar-labs",
      email: " employee@example.com ",
      password: "existing-password",
      rememberWorkspace: true,
    });

    expect(result.success).toBe(true);
    if (result.success) {
      expect(result.data.email).toBe("employee@example.com");
    }
  });

  it.each([
    "Northstar",
    "northstar_teams",
    "-northstar",
    "northstar-",
    "northstar--labs",
  ])("rejects invalid workspace slug %s", (workspaceSlug) => {
    const result = tenantLoginSchema.safeParse({
      workspaceSlug,
      email: "employee@example.com",
      password: "password",
      rememberWorkspace: false,
    });

    expect(result.success).toBe(false);
  });

  it("rejects passwords over the API maximum without requiring strength", () => {
    const result = tenantLoginSchema.safeParse({
      workspaceSlug: "northstar",
      email: "employee@example.com",
      password: "x".repeat(129),
      rememberWorkspace: false,
    });

    expect(result.success).toBe(false);
  });
});

describe("platformLoginSchema", () => {
  it("requires a valid email", () => {
    expect(
      platformLoginSchema.safeParse({
        email: "not-an-email",
        password: "some-password",
      }).success,
    ).toBe(false);
  });
});
