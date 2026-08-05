import {
  Ban,
  Building2,
  CircleCheck,
  CircleX,
  RefreshCcw,
  RotateCcw,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";

import type { PlatformActivity } from "../../model/dashboard";
import styles from "./RecentActivity.module.css";

interface RecentActivityProps {
  activity: PlatformActivity[];
}

interface ActivityCopy {
  detail: string | null;
  icon: LucideIcon;
  title: string;
  tone: "blue" | "green" | "orange" | "red" | "slate";
}

const timeFormatter = new Intl.DateTimeFormat(undefined, {
  hour: "numeric",
  minute: "2-digit",
});
const groupDateFormatter = new Intl.DateTimeFormat(undefined, {
  day: "numeric",
  month: "long",
  year: "numeric",
});

const readMetadata = (
  metadata: Record<string, unknown>,
  keys: string[],
): string | null => {
  for (const key of keys) {
    const value = metadata[key];
    if (typeof value === "string" && value.trim()) {
      return value.trim();
    }
  }
  return null;
};

const readOfferingName = (metadata: Record<string, unknown>): string => {
  const offering = metadata.offering;
  if (offering && typeof offering === "object") {
    const displayName = (offering as Record<string, unknown>).display_name;
    if (typeof displayName === "string" && displayName.trim()) {
      return displayName.trim();
    }
  }
  return "Offering";
};

const formatEventType = (eventType: string): string =>
  eventType
    .toLowerCase()
    .split("_")
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(" ");

const getActivityCopy = (event: PlatformActivity): ActivityCopy => {
  const tenantName = event.tenant.tenant_name;

  switch (event.event_type) {
    case "TENANT_CREATED":
      return {
        detail: "A new tenant workspace was registered.",
        icon: Building2,
        title: `${tenantName} created`,
        tone: "blue",
      };
    case "PLAN_CHANGED": {
      const fromPlan = readMetadata(event.metadata, [
        "from_plan_name",
        "from_plan",
      ]);
      const toPlan = readMetadata(event.metadata, ["to_plan_name", "to_plan"]);
      return {
        detail:
          fromPlan && toPlan
            ? `${fromPlan} to ${toPlan}`
            : "The tenant subscription was updated.",
        icon: RefreshCcw,
        title: `${tenantName} subscription changed`,
        tone: "orange",
      };
    }
    case "TENANT_SUSPENDED":
      return {
        detail: "Platform access was suspended.",
        icon: Ban,
        title: `${tenantName} suspended`,
        tone: "red",
      };
    case "TENANT_REACTIVATED":
    case "TENANT_ACTIVATED":
      return {
        detail: "Platform access was restored.",
        icon: RotateCcw,
        title: `${tenantName} reactivated`,
        tone: "green",
      };
    case "DATABASE_ALLOCATION_READY":
      return {
        detail: "The database allocation is ready.",
        icon: CircleCheck,
        title: `Database created for ${tenantName}`,
        tone: "green",
      };
    case "DATABASE_ALLOCATION_FAILED":
      return {
        detail: "The database allocation needs attention.",
        icon: CircleX,
        title: `Database setup failed for ${tenantName}`,
        tone: "red",
      };
    case "OFFERING_GRANTED": {
      const offeringName = readOfferingName(event.metadata);
      return {
        detail: "Time-bound workspace access was granted.",
        icon: CircleCheck,
        title: `${offeringName} granted to ${tenantName}`,
        tone: "green",
      };
    }
    case "OFFERING_SUSPENDED": {
      const offeringName = readOfferingName(event.metadata);
      return {
        detail: "Offering access was temporarily paused.",
        icon: Ban,
        title: `${offeringName} suspended for ${tenantName}`,
        tone: "orange",
      };
    }
    case "OFFERING_RESUMED": {
      const offeringName = readOfferingName(event.metadata);
      return {
        detail: "Offering access was restored.",
        icon: RotateCcw,
        title: `${offeringName} resumed for ${tenantName}`,
        tone: "green",
      };
    }
    case "OFFERING_DEACTIVATED": {
      const offeringName = readOfferingName(event.metadata);
      return {
        detail: "The entitlement was deactivated.",
        icon: CircleX,
        title: `${offeringName} deactivated for ${tenantName}`,
        tone: "red",
      };
    }
    case "OFFERING_EXPIRED": {
      const offeringName = readOfferingName(event.metadata);
      return {
        detail: "The entitlement reached its expiry date.",
        icon: CircleX,
        title: `${offeringName} expired for ${tenantName}`,
        tone: "slate",
      };
    }
    default:
      return {
        detail: "A platform event was recorded.",
        icon: RefreshCcw,
        title: `${tenantName}: ${formatEventType(event.event_type)}`,
        tone: "slate",
      };
  }
};

const localDayKey = (date: Date): string =>
  `${date.getFullYear()}-${date.getMonth()}-${date.getDate()}`;

const getGroupLabel = (date: Date): string => {
  const today = new Date();
  const todayStart = new Date(
    today.getFullYear(),
    today.getMonth(),
    today.getDate(),
  );
  const eventStart = new Date(
    date.getFullYear(),
    date.getMonth(),
    date.getDate(),
  );
  const dayDifference = Math.round(
    (todayStart.getTime() - eventStart.getTime()) / 86_400_000,
  );

  if (dayDifference === 0) {
    return "Today";
  }
  if (dayDifference === 1) {
    return "Yesterday";
  }
  return groupDateFormatter.format(date);
};

export const RecentActivity = ({ activity }: RecentActivityProps) => {
  const groups = activity.reduce<
    Array<{ date: Date; events: PlatformActivity[]; key: string }>
  >((result, event) => {
    const date = new Date(event.occurred_at);
    const key = localDayKey(date);
    const existingGroup = result.find((group) => group.key === key);
    if (existingGroup) {
      existingGroup.events.push(event);
    } else {
      result.push({ date, events: [event], key });
    }
    return result;
  }, []);

  return (
    <section className={styles.card} aria-labelledby="recent-activity-title">
      <header>
        <div>
          <p>Platform events</p>
          <h2 id="recent-activity-title">Recent activity</h2>
        </div>
        <span>Latest updates</span>
      </header>

      {groups.length === 0 ? (
        <div className={styles.empty}>
          <Building2 size={24} aria-hidden="true" />
          <strong>No platform activity yet</strong>
          <span>Tenant and infrastructure events will appear here.</span>
        </div>
      ) : (
        <div className={styles.groups}>
          {groups.map((group) => (
            <section key={group.key} aria-label={getGroupLabel(group.date)}>
              <h3>{getGroupLabel(group.date)}</h3>
              <ol>
                {group.events.map((event) => {
                  const copy = getActivityCopy(event);
                  const Icon = copy.icon;
                  return (
                    <li key={event.activity_id}>
                      <span
                        className={`${styles.eventIcon} ${styles[copy.tone]}`}
                        aria-hidden="true"
                      >
                        <Icon size={16} />
                      </span>
                      <div>
                        <strong>{copy.title}</strong>
                        {copy.detail && <p>{copy.detail}</p>}
                      </div>
                      <time dateTime={event.occurred_at}>
                        {timeFormatter.format(new Date(event.occurred_at))}
                      </time>
                    </li>
                  );
                })}
              </ol>
            </section>
          ))}
        </div>
      )}
    </section>
  );
};

