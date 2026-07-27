import { apiRequest } from "../../../shared/api/client";
import {
  ApiError,
  InvalidApiResponseError,
  NetworkError,
} from "../../../shared/api/errors";
import {
  parseDashboard,
  parseReadiness,
  type GrowthPeriod,
  type PlatformDashboard,
  type RegistrationPeriod,
  type SystemHealth,
} from "../model/dashboard";

export interface DashboardQuery {
  growthMonths: GrowthPeriod;
  registrationDays: RegistrationPeriod;
  activityLimit?: number;
}

export interface ReadinessResult {
  checkedAt: string | null;
  status: SystemHealth;
}

const parseOrThrow = <T>(parser: (payload: unknown) => T, payload: unknown): T => {
  try {
    return parser(payload);
  } catch {
    throw new InvalidApiResponseError();
  }
};

const getDashboard = async (
  query: DashboardQuery,
  signal?: AbortSignal,
): Promise<PlatformDashboard> => {
  const params = new URLSearchParams({
    growth_months: String(query.growthMonths),
    registration_days: String(query.registrationDays),
    activity_limit: String(query.activityLimit ?? 10),
  });
  const payload = await apiRequest<unknown>(
    `/platform/dashboard?${params.toString()}`,
    { signal },
  );
  return parseOrThrow(parseDashboard, payload);
};

const getReadiness = async (
  signal?: AbortSignal,
): Promise<ReadinessResult> => {
  try {
    const payload = await apiRequest<unknown>("/health/ready", {
      signal,
      notifyOnUnauthorized: false,
    });
    const readiness = parseOrThrow(parseReadiness, payload);
    return {
      checkedAt: readiness.checked_at,
      status: readiness.status,
    };
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") {
      throw error;
    }

    if (error instanceof ApiError && error.status === 503) {
      return { checkedAt: null, status: "degraded" };
    }

    if (
      error instanceof NetworkError ||
      error instanceof InvalidApiResponseError ||
      error instanceof ApiError
    ) {
      return { checkedAt: null, status: "unavailable" };
    }

    throw error;
  }
};

export const platformDashboardApi = {
  getDashboard,
  getReadiness,
};

