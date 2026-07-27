import { z } from "zod";

import type {
  PlatformLoginCredentials,
  SessionPrincipal,
  TenantLoginCredentials,
} from "../../../entities/session/model/session";
import { apiRequest } from "../../../shared/api/client";
import { InvalidApiResponseError } from "../../../shared/api/errors";

const platformPrincipalSchema = z.object({
  principal_type: z.literal("platform_admin"),
  principal_id: z.string().uuid(),
  name: z.string().min(1),
  email: z.string().email(),
  role: z.literal("Platform Admin"),
  tenant: z.null(),
});

const tenantPrincipalSchema = z.object({
  principal_type: z.literal("tenant_user"),
  principal_id: z.string().uuid(),
  name: z.string().min(1),
  email: z.string().email(),
  role: z.enum(["Tenant Admin", "Project Manager", "Employee"]),
  tenant: z.object({
    tenant_id: z.string().uuid(),
    org_name: z.string().min(1),
    workspace_slug: z.string().min(3).max(63),
    offerings: z.array(
      z.object({
        offering_id: z.string().uuid(),
        code: z.string().min(1),
        display_name: z.string().min(1),
        description: z.string(),
        icon_key: z.string().min(1),
        route_slug: z.string().min(1),
        sort_order: z.number().int().nonnegative(),
      }),
    ),
  }),
});

const sessionPrincipalSchema = z.discriminatedUnion("principal_type", [
  platformPrincipalSchema,
  tenantPrincipalSchema,
]);

const parsePrincipal = (value: unknown): SessionPrincipal => {
  const result = sessionPrincipalSchema.safeParse(value);
  if (!result.success) {
    throw new InvalidApiResponseError();
  }
  return result.data;
};

export const sessionApi = {
  restore: async (signal?: AbortSignal): Promise<SessionPrincipal> =>
    parsePrincipal(
      await apiRequest<unknown>("/auth/session", {
        signal,
        notifyOnUnauthorized: false,
      }),
    ),

  loginTenant: async (
    credentials: TenantLoginCredentials,
  ): Promise<SessionPrincipal> =>
    parsePrincipal(
      await apiRequest<unknown>("/auth/session/tenant", {
        method: "POST",
        body: credentials,
        notifyOnUnauthorized: false,
      }),
    ),

  loginPlatform: async (
    credentials: PlatformLoginCredentials,
  ): Promise<SessionPrincipal> =>
    parsePrincipal(
      await apiRequest<unknown>("/auth/session/platform", {
        method: "POST",
        body: credentials,
        notifyOnUnauthorized: false,
      }),
    ),

  logout: async (): Promise<void> => {
    await apiRequest<void>("/auth/session", {
      method: "DELETE",
      notifyOnUnauthorized: false,
    });
  },
};
