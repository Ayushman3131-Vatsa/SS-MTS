import {
  Building2,
  CalendarPlus,
  CircleAlert,
  CircleCheck,
  Database,
  HardDrive,
  ServerCog,
  UsersRound,
} from "lucide-react";

import type {
  PlatformDashboard,
  SystemHealth,
} from "../../model/dashboard";
import styles from "./DashboardSummary.module.css";

interface DashboardSummaryProps {
  health: SystemHealth | "checking";
  kpis: PlatformDashboard["kpis"];
}

const numberFormatter = new Intl.NumberFormat();

const healthContent = {
  checking: {
    detail: "Checking services",
    label: "Checking",
    tone: "neutral",
  },
  healthy: {
    detail: "API and database operational",
    label: "Healthy",
    tone: "success",
  },
  degraded: {
    detail: "Database check needs attention",
    label: "Degraded",
    tone: "warning",
  },
  unavailable: {
    detail: "Readiness service unavailable",
    label: "Unavailable",
    tone: "danger",
  },
} as const;

export const DashboardSummary = ({
  health,
  kpis,
}: DashboardSummaryProps) => {
  const primaryCards = [
    {
      detail: "Across the platform",
      icon: Building2,
      label: "Total Tenants",
      value: kpis.total_tenants,
    },
    {
      detail: "Ready and subscribed",
      icon: CircleCheck,
      label: "Active Tenants",
      value: kpis.active_tenants,
    },
    {
      detail: "Provisioned and ready",
      icon: HardDrive,
      label: "Dedicated Databases",
      value: kpis.dedicated_databases,
    },
    {
      detail: "On shared infrastructure",
      icon: Database,
      label: "Shared Database Tenants",
      value: kpis.shared_database_tenants,
    },
  ];
  const secondaryCards = [
    {
      detail: "All tenant accounts",
      icon: UsersRound,
      label: "Total Users",
      value: kpis.total_users,
    },
    {
      detail: "Current UTC month",
      icon: CalendarPlus,
      label: "New Tenants This Month",
      value: kpis.new_tenants_this_month,
    },
    {
      detail: "Require renewal",
      icon: CircleAlert,
      label: "Expired Subscriptions",
      value: kpis.expired_subscriptions,
    },
  ];
  const currentHealth = healthContent[health];

  return (
    <section aria-labelledby="platform-overview-title">
      <h2 id="platform-overview-title" className={styles.visuallyHidden}>
        Platform overview
      </h2>

      <div className={styles.grid}>
        {primaryCards.map(({ detail, icon: Icon, label, value }) => (
          <article className={styles.card} key={label}>
            <span className={styles.icon}>
              <Icon size={19} aria-hidden="true" />
            </span>
            <div className={styles.cardBody}>
              <p>{label}</p>
              <strong>{numberFormatter.format(value)}</strong>
              <span>{detail}</span>
            </div>
          </article>
        ))}
      </div>

      <div className={`${styles.grid} ${styles.secondaryGrid}`}>
        {secondaryCards.map(({ detail, icon: Icon, label, value }) => (
          <article className={styles.card} key={label}>
            <span className={`${styles.icon} ${styles.secondaryIcon}`}>
              <Icon size={19} aria-hidden="true" />
            </span>
            <div className={styles.cardBody}>
              <p>{label}</p>
              <strong>{numberFormatter.format(value)}</strong>
              <span>{detail}</span>
            </div>
          </article>
        ))}

        <article
          className={styles.card}
          aria-label={`System health: ${currentHealth.label}`}
        >
          <span className={`${styles.icon} ${styles.secondaryIcon}`}>
            <ServerCog size={19} aria-hidden="true" />
          </span>
          <div className={styles.cardBody}>
            <p>System Health</p>
            <strong
              className={`${styles.health} ${styles[currentHealth.tone]}`}
            >
              <span aria-hidden="true" />
              {currentHealth.label}
            </strong>
            <span>{currentHealth.detail}</span>
          </div>
        </article>
      </div>
    </section>
  );
};

