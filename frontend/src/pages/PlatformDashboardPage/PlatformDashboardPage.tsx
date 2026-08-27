import { RefreshCw } from "lucide-react";
import { useState } from "react";

import {
  GROWTH_PERIODS,
  REGISTRATION_PERIODS,
  type GrowthPeriod,
  type RegistrationPeriod,
} from "../../features/platform-dashboard/model/dashboard";
import { usePlatformDashboard } from "../../features/platform-dashboard/model/usePlatformDashboard";
import { DashboardCharts } from "../../features/platform-dashboard/ui/DashboardCharts/DashboardCharts";
import { DashboardSummary } from "../../features/platform-dashboard/ui/DashboardSummary/DashboardSummary";
import { RecentActivity } from "../../features/platform-dashboard/ui/RecentActivity/RecentActivity";
import { Alert } from "../../shared/ui/Alert/Alert";
import { Button } from "../../shared/ui/Button/Button";
import styles from "./PlatformDashboardPage.module.css";

const updatedAtFormatter = new Intl.DateTimeFormat(undefined, {
  day: "numeric",
  hour: "numeric",
  minute: "2-digit",
  month: "short",
});

const DashboardSkeleton = () => (
  <div className={styles.skeleton} role="status" aria-label="Loading dashboard">
    <span className={styles.visuallyHidden}>Loading platform dashboard…</span>
    <div className={styles.skeletonCards}>
      {Array.from({ length: 8 }, (_, index) => (
        <div key={index} />
      ))}
    </div>
    <div className={styles.skeletonChart} />
    <div className={styles.skeletonRow}>
      <div />
      <div />
    </div>
  </div>
);

export const PlatformDashboardPage = () => {
  const [growthMonths, setGrowthMonths] = useState<GrowthPeriod>(12);
  const [registrationDays, setRegistrationDays] =
    useState<RegistrationPeriod>(30);
  const {
    data,
    error,
    health,
    isInitialLoading,
    isRefreshing,
    lastSuccessfulAt,
    refresh,
  } = usePlatformDashboard({ growthMonths, registrationDays });
  const isLoading = isInitialLoading || isRefreshing;

  return (
    <div className={styles.page} aria-busy={isLoading}>
      <header className={styles.pageHeader}>
        <div>
          <h1>Dashboard</h1>
          <p>Tenant adoption, infrastructure, and subscriptions.</p>
        </div>
        <div className={styles.actions}>
          <div className={styles.filters}>
            <label>
              <span>Growth period</span>
              <select
                aria-label="Tenant growth period"
                value={growthMonths}
                onChange={(event) =>
                  setGrowthMonths(Number(event.target.value) as GrowthPeriod)
                }
              >
                {GROWTH_PERIODS.map((period) => (
                  <option key={period} value={period}>
                    Last {period} months
                  </option>
                ))}
              </select>
            </label>
            <label>
              <span>Registration period</span>
              <select
                aria-label="New registration period"
                value={registrationDays}
                onChange={(event) =>
                  setRegistrationDays(
                    Number(event.target.value) as RegistrationPeriod,
                  )
                }
              >
                {REGISTRATION_PERIODS.map((period) => (
                  <option key={period} value={period}>
                    Last {period} days
                  </option>
                ))}
              </select>
            </label>
          </div>
          <div className={styles.refreshGroup}>
            <span aria-live="polite">
              {lastSuccessfulAt
                ? `Updated ${updatedAtFormatter.format(new Date(lastSuccessfulAt))}`
                : "Waiting for data"}
            </span>
            <Button
              variant="secondary"
              loading={isLoading}
              loadingLabel="Refreshing…"
              onClick={() => void refresh()}
            >
              <RefreshCw size={16} aria-hidden="true" />
              Refresh
            </Button>
          </div>
        </div>
      </header>

      {isInitialLoading && !data ? (
        <DashboardSkeleton />
      ) : !data ? (
        <section className={styles.errorState} role="alert">
          <div>
            <h2>Dashboard unavailable</h2>
            <p>{error}</p>
            <Button onClick={() => void refresh()}>Try again</Button>
          </div>
        </section>
      ) : (
        <>
          {error && (
            <Alert tone="error" title="Data may be out of date">
              {error} Showing the last successful update.
            </Alert>
          )}
          <DashboardSummary health={health} kpis={data.kpis} />
          <DashboardCharts charts={data.charts} />
          <RecentActivity activity={data.recent_activity} />
        </>
      )}
    </div>
  );
};
