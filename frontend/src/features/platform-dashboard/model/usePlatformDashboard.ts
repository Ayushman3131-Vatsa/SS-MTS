import { useCallback, useEffect, useRef, useState } from "react";

import {
  InvalidApiResponseError,
  NetworkError,
} from "../../../shared/api/errors";
import { platformDashboardApi } from "../api/platform-dashboard-api";
import type {
  GrowthPeriod,
  PlatformDashboard,
  RegistrationPeriod,
  SystemHealth,
} from "./dashboard";

const REFRESH_INTERVAL_MS = 60_000;

interface UsePlatformDashboardOptions {
  activityLimit?: number;
  growthMonths: GrowthPeriod;
  registrationDays: RegistrationPeriod;
}

interface DashboardState {
  data: PlatformDashboard | null;
  error: string | null;
  health: SystemHealth | "checking";
  isInitialLoading: boolean;
  isRefreshing: boolean;
  lastSuccessfulAt: string | null;
  refresh: () => Promise<void>;
}

const getErrorMessage = (error: unknown): string => {
  if (error instanceof NetworkError) {
    return "The dashboard service could not be reached. Check your connection and try again.";
  }

  if (error instanceof InvalidApiResponseError) {
    return "The dashboard returned an unexpected response. Please try again.";
  }

  return "We could not load the platform dashboard. Please try again.";
};

export const usePlatformDashboard = ({
  activityLimit = 10,
  growthMonths,
  registrationDays,
}: UsePlatformDashboardOptions): DashboardState => {
  const [data, setData] = useState<PlatformDashboard | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [health, setHealth] = useState<SystemHealth | "checking">("checking");
  const [isInitialLoading, setIsInitialLoading] = useState(true);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [lastSuccessfulAt, setLastSuccessfulAt] = useState<string | null>(null);
  const dataRef = useRef<PlatformDashboard | null>(null);
  const controllerRef = useRef<AbortController | null>(null);

  const load = useCallback(async () => {
    controllerRef.current?.abort();
    const controller = new AbortController();
    controllerRef.current = controller;

    if (dataRef.current) {
      setIsRefreshing(true);
    } else {
      setIsInitialLoading(true);
    }

    try {
      const [dashboardResult, readinessResult] = await Promise.allSettled([
        platformDashboardApi.getDashboard(
          { activityLimit, growthMonths, registrationDays },
          controller.signal,
        ),
        platformDashboardApi.getReadiness(controller.signal),
      ]);

      if (controller.signal.aborted) {
        return;
      }

      setHealth(
        readinessResult.status === "fulfilled"
          ? readinessResult.value.status
          : "unavailable",
      );

      if (dashboardResult.status === "rejected") {
        throw dashboardResult.reason;
      }

      const nextData = dashboardResult.value;
      dataRef.current = nextData;
      setData(nextData);
      setLastSuccessfulAt(nextData.generated_at);
      setError(null);
    } catch (requestError) {
      if (
        requestError instanceof DOMException &&
        requestError.name === "AbortError"
      ) {
        return;
      }
      setError(getErrorMessage(requestError));
    } finally {
      if (controllerRef.current === controller) {
        setIsInitialLoading(false);
        setIsRefreshing(false);
      }
    }
  }, [activityLimit, growthMonths, registrationDays]);

  useEffect(() => {
    void load();

    let refreshTimer: number | undefined;
    const scheduleRefresh = () => {
      window.clearInterval(refreshTimer);
      if (document.visibilityState === "visible") {
        refreshTimer = window.setInterval(() => {
          void load();
        }, REFRESH_INTERVAL_MS);
      }
    };
    const refreshWhenVisible = () => {
      if (document.visibilityState === "visible") {
        void load();
      }
      scheduleRefresh();
    };
    const refreshOnFocus = () => {
      if (document.visibilityState === "visible") {
        void load();
      }
    };

    scheduleRefresh();
    document.addEventListener("visibilitychange", refreshWhenVisible);
    window.addEventListener("focus", refreshOnFocus);

    return () => {
      window.clearInterval(refreshTimer);
      document.removeEventListener("visibilitychange", refreshWhenVisible);
      window.removeEventListener("focus", refreshOnFocus);
      controllerRef.current?.abort();
    };
  }, [load]);

  return {
    data,
    error,
    health,
    isInitialLoading,
    isRefreshing,
    lastSuccessfulAt,
    refresh: load,
  };
};
