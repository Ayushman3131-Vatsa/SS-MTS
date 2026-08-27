import { z } from "zod";

import { apiRequest } from "../../../shared/api/client";
import { InvalidApiResponseError } from "../../../shared/api/errors";
import type {
  AccessLevel,
  DefaultRoleCreatePayload,
  DefaultRoleDetail,
  DefaultRoleListItem,
  DefaultRolePagesCatalog,
  DefaultRoleUpdatePayload,
} from "../model/default-roles";

const accessLevelSchema = z.enum(["none", "view", "modify"]);

const pageSchema = z.object({
  page_id: z.string().uuid(),
  page_code: z.string().min(1),
  module: z.string().min(1),
  page_name: z.string().min(1),
  route: z.string().min(1),
  app_scope: z.string().min(1),
  offering_code: z.string().nullable(),
});

const listItemSchema = z.object({
  role_id: z.string().uuid(),
  role_code: z.string().min(1),
  role_name: z.string().min(1),
  description: z.string().nullable(),
  offering_id: z.string().uuid().nullable(),
  offering_code: z.string().nullable(),
  offering_name: z.string().nullable(),
  module_scope: z.string().min(1),
  is_system: z.boolean(),
  is_active: z.boolean(),
  page_count: z.number().int().nonnegative(),
  modify_count: z.number().int().nonnegative(),
  view_count: z.number().int().nonnegative(),
  none_count: z.number().int().nonnegative(),
  version: z.number().int().positive(),
  created_at: z.string(),
  updated_at: z.string(),
});

const detailSchema = listItemSchema.extend({
  page_access: z.array(
    z.object({
      page: pageSchema,
      access_level: accessLevelSchema,
    }),
  ),
});

const pagesCatalogSchema = z.object({
  module_scope: z.string().min(1),
  offering_id: z.string().uuid().nullable(),
  offering_code: z.string().nullable(),
  offering_name: z.string().nullable(),
  pages: z.array(pageSchema),
});

const parse = <T>(schema: z.ZodType<T>, payload: unknown): T => {
  const result = schema.safeParse(payload);
  if (!result.success) {
    throw new InvalidApiResponseError();
  }
  return result.data;
};

interface ListOptions {
  offeringId?: string | null;
  coreOnly?: boolean;
  signal?: AbortSignal;
}

export const defaultRolesApi = {
  list: async ({ offeringId, coreOnly, signal }: ListOptions = {}): Promise<DefaultRoleListItem[]> => {
    const query = new URLSearchParams();
    if (offeringId) query.set("offering_id", offeringId);
    else if (coreOnly) query.set("scope", "CORE");
    const suffix = query.size > 0 ? `?${query.toString()}` : "";
    return parse(z.array(listItemSchema), await apiRequest<unknown>(`/platform/default-roles${suffix}`, { signal }));
  },

  pages: async ({ offeringId, signal }: { offeringId?: string | null; signal?: AbortSignal }): Promise<DefaultRolePagesCatalog> => {
    const query = new URLSearchParams();
    if (offeringId) query.set("offering_id", offeringId);
    const suffix = query.size > 0 ? `?${query.toString()}` : "";
    return parse(pagesCatalogSchema, await apiRequest<unknown>(`/platform/default-roles/pages${suffix}`, { signal }));
  },

  get: async (roleId: string, signal?: AbortSignal): Promise<DefaultRoleDetail> =>
    parse(detailSchema, await apiRequest<unknown>(`/platform/default-roles/${roleId}`, { signal })),

  create: async (payload: DefaultRoleCreatePayload): Promise<DefaultRoleDetail> =>
    parse(
      detailSchema,
      await apiRequest<unknown>("/platform/default-roles", {
        method: "POST",
        body: payload,
      }),
    ),

  update: async (roleId: string, payload: DefaultRoleUpdatePayload): Promise<DefaultRoleDetail> =>
    parse(
      detailSchema,
      await apiRequest<unknown>(`/platform/default-roles/${roleId}`, {
        method: "PATCH",
        body: payload,
      }),
    ),

  delete: async (roleId: string): Promise<void> => {
    await apiRequest<unknown>(`/platform/default-roles/${roleId}`, { method: "DELETE" });
  },
};

export type { AccessLevel };
