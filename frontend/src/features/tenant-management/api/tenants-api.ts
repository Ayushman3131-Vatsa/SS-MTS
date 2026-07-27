import { z } from "zod";

import { apiRequest } from "../../../shared/api/client";
import { InvalidApiResponseError } from "../../../shared/api/errors";
import type {
  TenantRecord,
  TenantRegistrationOptions,
  TenantRegistrationPayload,
} from "../model/tenants";

const offeringSchema = z.object({
  offering_id: z.string().uuid(),
  code: z.string().min(1),
  display_name: z.string().min(1),
  description: z.string(),
  icon_key: z.string().min(1),
  route_slug: z.string().min(1),
  sort_order: z.number().int().nonnegative(),
});

const decimalSchema = z
  .union([z.number().finite(), z.string().regex(/^-?\d+(?:\.\d+)?$/)])
  .nullable();

const tenantSchema = z.object({
  tenant_id: z.string().uuid(),
  org_name: z.string().min(1),
  tenant_code: z.string().min(1),
  workspace_slug: z.string().min(1),
  legal_name: z.string().nullable(),
  industry: z.string().nullable(),
  company_size: z.string().nullable(),
  website: z.string().nullable(),
  registration_number: z.string().nullable(),
  tax_identifier: z.string().nullable(),
  address_line_1: z.string().nullable(),
  address_line_2: z.string().nullable(),
  city: z.string().nullable(),
  state_province: z.string().nullable(),
  country: z.string().nullable(),
  postal_code: z.string().nullable(),
  contact_name: z.string().nullable(),
  contact_email: z.string().nullable(),
  contact_phone: z.string().nullable(),
  subscription_plan: z.string().min(1),
  subscription_plan_code: z.string().min(1),
  subscription_ends_at: z.string().nullable(),
  status: z.string().min(1),
  database_mode: z.string().min(1),
  database_provisioning_state: z.string().min(1),
  user_count: z.number().int().nonnegative(),
  offerings: z.array(offeringSchema),
  created_by_admin_id: z.string().uuid(),
  created_at: z.string(),
  updated_at: z.string(),
});

const optionsSchema = z.object({
  plans: z.array(
    z.object({
      code: z.string().min(1),
      display_name: z.string().min(1),
      // Pydantic intentionally serializes Decimal values as JSON strings to
      // preserve precision. Normalize them at the API boundary so the rest of
      // the UI has one stable numeric representation.
      price: decimalSchema,
      currency: z.string().nullable(),
      billing_interval: z.string().nullable(),
      max_users: z.number().int().positive().nullable(),
      requires_end_date: z.boolean(),
    }),
  ),
  offerings: z.array(offeringSchema),
  statuses: z.array(z.string().min(1)),
  database_modes: z.array(z.string().min(1)),
  defaults: z.object({
    subscription_plan_code: z.string().min(1),
    status: z.string().min(1),
    database_mode: z.string().min(1),
  }),
});

const parse = <T>(schema: z.ZodType<T>, payload: unknown): T => {
  const result = schema.safeParse(payload);
  if (!result.success) {
    throw new InvalidApiResponseError();
  }
  return result.data;
};

export const tenantsApi = {
  getRegistrationOptions: async (
    signal?: AbortSignal,
  ): Promise<TenantRegistrationOptions> => {
    const options = parse(
      optionsSchema,
      await apiRequest<unknown>("/tenants/registration-options", { signal }),
    );
    return {
      ...options,
      plans: options.plans.map((plan) => ({
        ...plan,
        price: typeof plan.price === "string" ? Number(plan.price) : plan.price,
      })),
    };
  },

  list: async (signal?: AbortSignal): Promise<TenantRecord[]> =>
    parse(
      z.array(tenantSchema),
      await apiRequest<unknown>("/tenants", { signal }),
    ),

  get: async (tenantId: string, signal?: AbortSignal): Promise<TenantRecord> =>
    parse(
      tenantSchema,
      await apiRequest<unknown>(`/tenants/${tenantId}`, { signal }),
    ),

  create: async (
    payload: TenantRegistrationPayload,
  ): Promise<TenantRecord> =>
    parse(
      tenantSchema,
      await apiRequest<unknown>("/tenants", {
        method: "POST",
        body: payload,
      }),
    ),
};
