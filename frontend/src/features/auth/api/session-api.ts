import { z } from "zod";



import type {

  PasswordChangeCredentials,

  PlatformLoginCredentials,

  SessionPrincipal,

  TenantLoginCredentials,

} from "../../../entities/session/model/session";

import { apiRequest } from "../../../shared/api/client";

import { InvalidApiResponseError } from "../../../shared/api/errors";



const pageAccessSchema = z.object({

  page_code: z.string().min(1),

  module: z.string().min(1),

  page_name: z.string().min(1),

  route: z.string().min(1),

  access_level: z.enum(["none", "view", "modify"]),

  offering_code: z.string().nullable(),

});



const platformPrincipalSchema = z.object({

  principal_type: z.literal("platform_admin"),

  principal_id: z.string().uuid(),

  name: z.string().min(1),

  email: z.string().email(),

  username: z.string().min(1).optional(),

  role: z.string().min(1),

  roles: z.array(z.string()).optional().default([]),

  page_access: z.array(pageAccessSchema).optional().default([]),

  tenant: z.null(),

  password_change_required: z.boolean().optional().default(false),

});



const tenantPrincipalSchema = z.object({

  principal_type: z.literal("tenant_user"),

  principal_id: z.string().uuid(),

  name: z.string().min(1),

  email: z.string().email().nullable().optional().default(null),

  username: z.string().min(1).optional(),

  role: z.string().min(1),

  roles: z.array(z.string()).optional().default([]),

  page_access: z.array(pageAccessSchema).optional().default([]),

  password_change_required: z.boolean(),

  tenant: z.object({

    tenant_id: z.string().uuid(),

    org_name: z.string().min(1),

    tenant_code: z.string().min(2).max(30),

    status: z.enum(["ACTIVE", "SUSPENDED"]),

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



  changePassword: async (

    credentials: PasswordChangeCredentials,

  ): Promise<SessionPrincipal> => {

    const value = await apiRequest<unknown>("/auth/password/change", {

      method: "POST",

      body: credentials,

      notifyOnUnauthorized: false,

    });

    const result = z.object({ principal: sessionPrincipalSchema }).safeParse(value);

    if (!result.success) throw new InvalidApiResponseError();

    return result.data.principal;

  },



  logout: async (): Promise<void> => {

    await apiRequest<void>("/auth/session", {

      method: "DELETE",

      notifyOnUnauthorized: false,

    });

  },

};


