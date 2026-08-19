import { z } from "zod";

export const GROWTH_PERIODS = [6, 12, 24] as const;
export const REGISTRATION_PERIODS = [7, 30, 90] as const;

export type GrowthPeriod = (typeof GROWTH_PERIODS)[number];
export type RegistrationPeriod = (typeof REGISTRATION_PERIODS)[number];

const nonNegativeInteger = z.number().int().nonnegative();
const dateOnly = z.string().regex(/^\d{4}-\d{2}-\d{2}$/);
const utcDateTime = z.string().datetime({ offset: true });

const dashboardSchema = z.object({
  generated_at: utcDateTime,
  filters: z.object({
    growth_months: z.union([z.literal(6), z.literal(12), z.literal(24)]),
    registration_days: z.union([
      z.literal(7),
      z.literal(30),
      z.literal(90),
    ]),
  }),
  kpis: z.object({
    total_tenants: nonNegativeInteger,
    active_tenants: nonNegativeInteger,
    dedicated_databases: nonNegativeInteger,
    shared_database_tenants: nonNegativeInteger,
    total_users: nonNegativeInteger,
    new_tenants_this_month: nonNegativeInteger,
    expired_subscriptions: nonNegativeInteger,
  }),
  charts: z.object({
    tenant_growth: z.array(
      z.object({
        month: dateOnly,
        total_tenants: nonNegativeInteger,
      }),
    ),
    new_registrations: z.array(
      z.object({
        date: dateOnly,
        new_tenants: nonNegativeInteger,
      }),
    ),
    subscription_distribution: z.array(
      z.object({
        plan_code: z.string().regex(/^[A-Z][A-Z0-9_]{0,49}$/),
        plan_name: z.string().min(1),
        tenant_count: nonNegativeInteger,
      }),
    ),
  }),
  recent_activity: z.array(
    z.object({
      activity_id: z.string().uuid(),
      // Event codes are an append-only backend catalog. Keep structural
      // validation strict without making a newly deployed event type take the
      // entire dashboard offline; the activity UI has a safe fallback label.
      event_type: z.string().regex(/^[A-Z][A-Z0-9_]{0,63}$/),
      occurred_at: utcDateTime,
      tenant: z.object({
        tenant_id: z.string().uuid().nullable(),
        tenant_name: z.string().min(1),
      }),
      metadata: z.record(z.unknown()),
    }),
  ),
});

export const readinessSchema = z.object({
  status: z.enum(["healthy", "degraded"]),
  checked_at: utcDateTime,
  checks: z.object({
    api: z.literal("healthy"),
    database: z.enum(["healthy", "unavailable"]),
  }),
});

export type PlatformDashboard = z.infer<typeof dashboardSchema>;
export type PlatformActivity = PlatformDashboard["recent_activity"][number];
export type ReadinessResponse = z.infer<typeof readinessSchema>;
export type SystemHealth = ReadinessResponse["status"] | "unavailable";

export const parseDashboard = (payload: unknown): PlatformDashboard =>
  dashboardSchema.parse(payload);

export const parseReadiness = (payload: unknown): ReadinessResponse =>
  readinessSchema.parse(payload);
