import { z } from "zod";

import { apiRequest } from "../../../shared/api/client";
import { InvalidApiResponseError } from "../../../shared/api/errors";
import type {
  DefaultTemplateCreatePayload,
  DefaultTemplateDetail,
  DefaultTemplateListItem,
  DefaultTemplatePreview,
  DefaultTemplatePreviewPayload,
  DefaultTemplateUpdatePayload,
} from "../model/default-templates";

const templateTypeSchema = z.enum(["EMAIL", "LETTER", "NOTIFICATION", "OTHER"]);

const placeholderSchema = z.object({
  key: z.string().regex(/^[a-z][a-z0-9_]{0,63}$/),
  label: z.string().min(1).max(100),
  sample_value: z.string().max(1_000),
  required: z.boolean(),
});

const templateListItemSchema = z.object({
  template_id: z.string().uuid(),
  offering_id: z.string().uuid(),
  offering_code: z.string().min(1),
  offering_name: z.string().min(1),
  category_id: z.string().uuid(),
  category_code: z.string().min(1),
  category_name: z.string().min(1),
  code: z.string().regex(/^[a-z][a-z0-9_]{0,99}$/),
  name: z.string().min(1).max(200),
  description: z.string().max(5_000),
  type: templateTypeSchema,
  subject: z.string().max(500).nullable(),
  sort_order: z.number().int().nonnegative(),
  is_active: z.boolean(),
  version: z.number().int().positive(),
  created_at: z.string(),
  updated_at: z.string(),
  inheriting_tenant_count: z.number().int().nonnegative(),
  customized_tenant_count: z.number().int().nonnegative(),
});

const templateDetailSchema = templateListItemSchema.extend({
  body: z.string().min(1).max(50_000),
  placeholders: z.array(placeholderSchema).max(100),
});

const templatePreviewSchema = z.object({
  subject: z.string().nullable(),
  rendered_body: z.string(),
});

const parse = <T>(schema: z.ZodType<T>, payload: unknown): T => {
  const result = schema.safeParse(payload);
  if (!result.success) {
    throw new InvalidApiResponseError();
  }
  return result.data;
};

interface ListOptions {
  offeringId?: string;
  signal?: AbortSignal;
}

export const defaultTemplatesApi = {
  list: async ({ offeringId, signal }: ListOptions): Promise<DefaultTemplateListItem[]> => {
    const query = new URLSearchParams();
    if (offeringId) query.set("offering_id", offeringId);
    const queryString = query.size > 0 ? `?${query.toString()}` : "";
    return parse(
      z.array(templateListItemSchema),
      await apiRequest<unknown>(`/platform/default-templates${queryString}`, { signal }),
    );
  },

  get: async (templateId: string, signal?: AbortSignal): Promise<DefaultTemplateDetail> =>
    parse(
      templateDetailSchema,
      await apiRequest<unknown>(`/platform/default-templates/${templateId}`, { signal }),
    ),

  create: async (payload: DefaultTemplateCreatePayload): Promise<DefaultTemplateDetail> =>
    parse(
      templateDetailSchema,
      await apiRequest<unknown>("/platform/default-templates", {
        method: "POST",
        body: payload,
      }),
    ),

  update: async (
    templateId: string,
    payload: DefaultTemplateUpdatePayload,
  ): Promise<DefaultTemplateDetail> =>
    parse(
      templateDetailSchema,
      await apiRequest<unknown>(`/platform/default-templates/${templateId}`, {
        method: "PATCH",
        body: payload,
      }),
    ),

  preview: async (payload: DefaultTemplatePreviewPayload): Promise<DefaultTemplatePreview> =>
    parse(
      templatePreviewSchema,
      await apiRequest<unknown>("/platform/default-templates/preview", {
        method: "POST",
        body: payload,
      }),
    ),
};
