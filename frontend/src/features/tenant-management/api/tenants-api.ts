import { z } from "zod";

import { apiRequest } from "../../../shared/api/client";
import { InvalidApiResponseError } from "../../../shared/api/errors";
import type {
  TenantRecord,
  TenantListResponse,
  TenantOfferingActionPayload,
  TenantOfferingGrantPayload,
  TenantOfferingRemovalPayload,
  TenantOfferingEntitlement,
  TenantOfferingEvent,
  TenantStatusActionPayload,
  OfferingCatalogEntry,
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

const catalogOfferingSchema = offeringSchema.extend({
  status: z.string().min(1),
});

const entitlementSchema = offeringSchema.extend({
  entitlement_id: z.string().uuid(),
  status: z.string().min(1),
  starts_at: z.string(),
  ends_at: z.string().nullable(),
  suspended_at: z.string().nullable(),
  deactivated_at: z.string().nullable(),
  reason: z.string().nullable(),
  version: z.number().int().positive(),
  created_at: z.string(),
  updated_at: z.string(),
});

const eventSchema = z.object({
  event_id: z.string().uuid(),
  entitlement_id: z.string().uuid(),
  tenant_id: z.string().uuid(),
  event_type: z.string().min(1),
  actor_admin_id: z.string().uuid().nullable(),
  occurred_at: z.string(),
  old_value: z.record(z.unknown()).nullable(),
  new_value: z.record(z.unknown()).nullable(),
});

const decimalSchema = z
  .union([z.number().finite(), z.string().regex(/^-?\d+(?:\.\d+)?$/)])
  .nullable();

const tenantSchema = z.object({
  tenant_id: z.string().uuid(),
  org_name: z.string().min(1),
  tenant_code: z.string().min(1),
  legal_name: z.string().nullable(),
  industry: z.string().nullable(),
  company_size: z.string().nullable(),
  website: z.string().nullable(),
  tax_registration_number: z.string().nullable(),
  pan_number: z.string().nullable(),
  address_line_1: z.string().nullable(),
  address_line_2: z.string().nullable(),
  city: z.string().nullable(),
  state_province: z.string().nullable(),
  country: z.string().nullable(),
  postal_code: z.string().nullable(),
  contact_name: z.string().nullable(),
  contact_designation: z.string().nullable(),
  contact_email: z.string().nullable(),
  contact_phone: z.string().nullable(),
  alternate_contact_name: z.string().nullable().optional(),
  alternate_contact_designation: z.string().nullable().optional(),
  alternate_contact_email: z.string().nullable().optional(),
  alternate_contact_phone: z.string().nullable().optional(),
  subscription_plan: z.string().min(1),
  subscription_plan_code: z.string().min(1),
  subscription_ends_at: z.string().nullable(),
  status: z.string().min(1),
  database_mode: z.string().min(1),
  database_provisioning_state: z.string().min(1),
  user_count: z.number().int().nonnegative(),
  offerings: z.array(entitlementSchema),
  created_by_admin_id: z.string().uuid(),
  created_at: z.string(),
  updated_at: z.string(),
  version: z.number().int().positive(),
});

const tenantListSchema = z.object({
  items: z.array(tenantSchema),
  page: z.number().int().positive(),
  page_size: z.number().int().positive(),
  total: z.number().int().nonnegative(),
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

const idempotencyKey = () =>
  typeof crypto.randomUUID === "function"
    ? crypto.randomUUID()
    : `${Date.now()}-${Math.random().toString(16).slice(2)}`;

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

  list: async (
    params: { page?: number; pageSize?: number; query?: string; status?: string } = {},
    signal?: AbortSignal,
  ): Promise<TenantListResponse> =>
    parse(
      tenantListSchema,
      await apiRequest<unknown>(
        `/tenants?${new URLSearchParams({
          page: String(params.page ?? 1),
          page_size: String(params.pageSize ?? 25),
          ...(params.query ? { query: params.query } : {}),
          ...(params.status ? { status: params.status } : {}),
        })}`,
        { signal },
      ),
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

  catalog: async (signal?: AbortSignal): Promise<OfferingCatalogEntry[]> =>
    parse(z.array(catalogOfferingSchema), await apiRequest<unknown>("/tenants/offering-catalog", { signal })),

  entitlements: async (
    tenantId: string,
    signal?: AbortSignal,
  ): Promise<TenantOfferingEntitlement[]> =>
    parse(
      z.array(entitlementSchema),
      await apiRequest<unknown>(`/tenants/${tenantId}/offering-entitlements`, { signal }),
    ),

  history: async (
    tenantId: string,
    signal?: AbortSignal,
  ): Promise<TenantOfferingEvent[]> =>
    parse(
      z.array(eventSchema),
      await apiRequest<unknown>(
        `/tenants/${tenantId}/offering-entitlements/history`,
        { signal },
      ),
    ),

  grant: async (
    tenantId: string,
    payload: TenantOfferingGrantPayload,
  ): Promise<TenantOfferingEntitlement> =>
    parse(
      entitlementSchema,
      await apiRequest<unknown>(`/tenants/${tenantId}/offering-entitlements`, {
        method: "POST",
        headers: { "Idempotency-Key": idempotencyKey() },
        body: payload,
      }),
    ),

  tenantAction: async (
    tenantId: string,
    action: "suspend" | "activate",
    payload: TenantStatusActionPayload,
  ): Promise<TenantRecord> =>
    parse(
      tenantSchema,
      await apiRequest<unknown>(`/tenants/${tenantId}/${action}`, {
        method: "POST",
        headers: { "Idempotency-Key": idempotencyKey() },
        body: payload,
      }),
    ),

  offeringAction: async (
    tenantId: string,
    entitlementId: string,
    action: "suspend" | "resume" | "deactivate",
    payload: TenantOfferingActionPayload,
  ): Promise<TenantOfferingEntitlement> =>
    parse(
      entitlementSchema,
      await apiRequest<unknown>(
        `/tenants/${tenantId}/offering-entitlements/${entitlementId}/${action}`,
        {
          method: "POST",
          headers: { "Idempotency-Key": idempotencyKey() },
          body: payload,
        },
      ),
    ),

  removeEntitlement: async (
    tenantId: string,
    entitlementId: string,
    payload: TenantOfferingRemovalPayload,
  ): Promise<void> =>
    apiRequest<void>(
      `/tenants/${tenantId}/offering-entitlements/${entitlementId}`,
      {
        method: "DELETE",
        body: payload,
      },
    ),
};
