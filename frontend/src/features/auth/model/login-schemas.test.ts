import { describe, expect, it } from "vitest";

import { platformLoginSchema, tenantLoginSchema } from "./login-schemas";

describe("tenantLoginSchema", () => {
  it("accepts a valid login without applying account-creation password rules", () => {
    const result = tenantLoginSchema.safeParse({
      tenant_code: "acme",
      email: " employee@example.com ",
      password: "existing-password",
    });

    expect(result.success).toBe(true);
    if (result.success) {
      expect(result.data.email).toBe("employee@example.com");
      expect(result.data.tenant_code).toBe("ACME");
    }
  });

  it("accepts a username in place of email", () => {
    const result = tenantLoginSchema.safeParse({
      tenant_code: "ACME",
      email: "jane.doe",
      password: "existing-password",
    });
    expect(result.success).toBe(true);
  });

  it("rejects passwords over the API maximum without requiring strength", () => {
    const result = tenantLoginSchema.safeParse({
      tenant_code: "ACME",
      email: "employee@example.com",
      password: "x".repeat(129),
    });

    expect(result.success).toBe(false);
  });
});

describe("platformLoginSchema", () => {
  it("accepts a username or an email", () => {
    expect(
      platformLoginSchema.safeParse({
        email: "platform.admin",
        password: "some-password",
      }).success,
    ).toBe(true);
    expect(
      platformLoginSchema.safeParse({
        email: "ab",
        password: "some-password",
      }).success,
    ).toBe(false);
  });
});
