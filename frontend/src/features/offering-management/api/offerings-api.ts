import { z } from "zod";

import { apiRequest } from "../../../shared/api/client";
import { InvalidApiResponseError } from "../../../shared/api/errors";
import type { OfferingCatalogItem, OfferingCreatePayload, OfferingListParams, OfferingUpdatePayload } from "../model/offerings";

const offeringSchema = z.object({
  offering_id: z.string().uuid(),
  code: z.string().min(1),
  display_name: z.string().min(1),
  description: z.string(),
  icon_key: z.string().min(1),
  route_slug: z.string().min(1),
  sort_order: z.number().int().nonnegative(),
  status: z.enum(["ACTIVE", "INACTIVE"]),
  role_type: z.enum(["PLATFORM", "TENANT", "BOTH"]).default("TENANT"),
  tenant_entitlement_count: z.number().int().nonnegative(),
  configuration_category_count: z.number().int().nonnegative(),
});

const parse = <T>(schema: z.ZodType<T>, payload: unknown): T => {
  const result = schema.safeParse(payload);
  if (!result.success) throw new InvalidApiResponseError();
  return result.data;
};

export const offeringsApi = {
  list: async (signal?: AbortSignal, params: OfferingListParams = {}): Promise<OfferingCatalogItem[]> => {
    const query = new URLSearchParams();
    if (params.query) query.set("query", params.query);
    if (params.roleType) query.set("role_type", params.roleType);
    if (params.status) query.set("status", params.status);
    const suffix = query.size > 0 ? `?${query.toString()}` : "";
    return parse(z.array(offeringSchema), await apiRequest<unknown>(`/offerings${suffix}`, { signal }));
  },

  create: async (payload: OfferingCreatePayload): Promise<OfferingCatalogItem> =>
    parse(offeringSchema, await apiRequest<unknown>("/offerings", { method: "POST", body: payload })),

  update: async (offeringId: string, payload: OfferingUpdatePayload): Promise<OfferingCatalogItem> =>
    parse(offeringSchema, await apiRequest<unknown>(`/offerings/${offeringId}`, { method: "PATCH", body: payload })),

  setStatus: async (offeringId: string, status: "ACTIVE" | "INACTIVE"): Promise<OfferingCatalogItem> =>
    parse(
      offeringSchema,
      await apiRequest<unknown>(`/offerings/${offeringId}/${status === "ACTIVE" ? "activate" : "deactivate"}`, { method: "POST" }),
    ),

  remove: async (offeringId: string, reason: string): Promise<void> =>
    apiRequest<void>(`/offerings/${offeringId}`, { method: "DELETE", body: { reason } }),
};
