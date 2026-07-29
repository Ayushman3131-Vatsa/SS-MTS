import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { useReducedMotion } from "../../../../shared/model/useReducedMotion";
import type { PlatformDashboard } from "../../model/dashboard";
import styles from "./DashboardCharts.module.css";

interface DashboardChartsProps {
  charts: PlatformDashboard["charts"];
}

const numberFormatter = new Intl.NumberFormat();
const monthFormatter = new Intl.DateTimeFormat(undefined, {
  month: "short",
  timeZone: "UTC",
  year: "2-digit",
});
const dayFormatter = new Intl.DateTimeFormat(undefined, {
  day: "numeric",
  month: "short",
  timeZone: "UTC",
});
const fullDateFormatter = new Intl.DateTimeFormat(undefined, {
  day: "numeric",
  month: "long",
  timeZone: "UTC",
  year: "numeric",
});

const PIE_COLORS = ["#2563eb", "#0f766e", "#7c3aed", "#c2410c"];

const asUtcDate = (date: string) => new Date(`${date}T00:00:00Z`);

const EmptyChart = ({ message }: { message: string }) => (
  <div className={styles.empty}>
    <span aria-hidden="true" />
    <p>{message}</p>
  </div>
);

export const DashboardCharts = ({ charts }: DashboardChartsProps) => {
  const reducedMotion = useReducedMotion();
  const subscriptionTotal = charts.subscription_distribution.reduce(
    (total, item) => total + item.tenant_count,
    0,
  );

  return (
    <section className={styles.layout} aria-label="Platform analytics">
      <article className={`${styles.chartCard} ${styles.growthCard}`}>
        <header>
          <div>
            <p>Portfolio</p>
            <h2>Tenant growth over time</h2>
          </div>
          <span>Cumulative tenants</span>
        </header>
        {charts.tenant_growth.length === 0 ? (
          <EmptyChart message="Tenant growth will appear after the first tenant is registered." />
        ) : (
          <>
            <div
              className={styles.chart}
              role="group"
              aria-label="Line chart showing cumulative tenant growth by month"
            >
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart
                  accessibilityLayer
                  data={charts.tenant_growth}
                  margin={{ bottom: 4, left: -16, right: 8, top: 12 }}
                >
                  <defs>
                    <linearGradient id="tenantGrowthFill" x1="0" x2="0" y1="0" y2="1">
                      <stop offset="0%" stopColor="#2563eb" stopOpacity={0.24} />
                      <stop offset="100%" stopColor="#2563eb" stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid stroke="#e2e8f0" strokeDasharray="3 4" vertical={false} />
                  <XAxis
                    axisLine={false}
                    dataKey="month"
                    fontSize={11}
                    tickFormatter={(value: string) =>
                      monthFormatter.format(asUtcDate(value))
                    }
                    tickLine={false}
                    tickMargin={10}
                  />
                  <YAxis
                    allowDecimals={false}
                    axisLine={false}
                    fontSize={11}
                    tickLine={false}
                    width={40}
                  />
                  <Tooltip
                    formatter={(value) => [
                      numberFormatter.format(Number(value)),
                      "Total tenants",
                    ]}
                    labelFormatter={(value) =>
                      fullDateFormatter.format(asUtcDate(String(value)))
                    }
                  />
                  <Area
                    dataKey="total_tenants"
                    fill="url(#tenantGrowthFill)"
                    isAnimationActive={!reducedMotion}
                    name="Total tenants"
                    stroke="#2563eb"
                    strokeWidth={2.5}
                    type="monotone"
                  />
                </AreaChart>
              </ResponsiveContainer>
            </div>
            <details className={styles.dataTable}>
              <summary>View tenant growth data</summary>
              <table>
                <thead>
                  <tr>
                    <th scope="col">Month</th>
                    <th scope="col">Total tenants</th>
                  </tr>
                </thead>
                <tbody>
                  {charts.tenant_growth.map((point) => (
                    <tr key={point.month}>
                      <td>{fullDateFormatter.format(asUtcDate(point.month))}</td>
                      <td>{numberFormatter.format(point.total_tenants)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </details>
          </>
        )}
      </article>

      <article className={styles.chartCard}>
        <header>
          <div>
            <p>Acquisition</p>
            <h2>New registrations</h2>
          </div>
          <span>Tenants per day</span>
        </header>
        {charts.new_registrations.length === 0 ? (
          <EmptyChart message="Registration activity will appear here." />
        ) : (
          <>
            <div
              className={styles.chart}
              role="group"
              aria-label="Bar chart showing new tenant registrations by day"
            >
              <ResponsiveContainer width="100%" height="100%">
                <BarChart
                  accessibilityLayer
                  data={charts.new_registrations}
                  margin={{ bottom: 4, left: -18, right: 4, top: 12 }}
                >
                  <CartesianGrid stroke="#e2e8f0" strokeDasharray="3 4" vertical={false} />
                  <XAxis
                    axisLine={false}
                    dataKey="date"
                    fontSize={10}
                    interval="preserveStartEnd"
                    tickFormatter={(value: string) =>
                      dayFormatter.format(asUtcDate(value))
                    }
                    tickLine={false}
                    tickMargin={10}
                  />
                  <YAxis
                    allowDecimals={false}
                    axisLine={false}
                    fontSize={11}
                    tickLine={false}
                    width={36}
                  />
                  <Tooltip
                    formatter={(value) => [
                      numberFormatter.format(Number(value)),
                      "New tenants",
                    ]}
                    labelFormatter={(value) =>
                      fullDateFormatter.format(asUtcDate(String(value)))
                    }
                  />
                  <Bar
                    dataKey="new_tenants"
                    fill="#3b82f6"
                    isAnimationActive={!reducedMotion}
                    name="New tenants"
                    radius={[4, 4, 0, 0]}
                  />
                </BarChart>
              </ResponsiveContainer>
            </div>
            <details className={styles.dataTable}>
              <summary>View registration data</summary>
              <table>
                <thead>
                  <tr>
                    <th scope="col">Date</th>
                    <th scope="col">New tenants</th>
                  </tr>
                </thead>
                <tbody>
                  {charts.new_registrations.map((point) => (
                    <tr key={point.date}>
                      <td>{fullDateFormatter.format(asUtcDate(point.date))}</td>
                      <td>{numberFormatter.format(point.new_tenants)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </details>
          </>
        )}
      </article>

      <article className={styles.chartCard}>
        <header>
          <div>
            <p>Plans</p>
            <h2>Subscription distribution</h2>
          </div>
          <span>Current plans</span>
        </header>
        {subscriptionTotal === 0 ? (
          <EmptyChart message="Subscription distribution will appear here." />
        ) : (
          <>
            <div className={styles.distribution}>
              <div
                className={styles.pieChart}
                role="group"
                aria-label={`Donut chart showing ${numberFormatter.format(subscriptionTotal)} tenant subscriptions by plan`}
              >
                <ResponsiveContainer width="100%" height="100%">
                  <PieChart accessibilityLayer>
                    <Tooltip
                      formatter={(value) => [
                        numberFormatter.format(Number(value)),
                        "Tenants",
                      ]}
                    />
                    <Pie
                      data={charts.subscription_distribution}
                      dataKey="tenant_count"
                      innerRadius="65%"
                      isAnimationActive={!reducedMotion}
                      nameKey="plan_name"
                      outerRadius="90%"
                      paddingAngle={2}
                      stroke="none"
                    >
                      {charts.subscription_distribution.map((entry, index) => (
                        <Cell
                          fill={PIE_COLORS[index % PIE_COLORS.length]}
                          key={entry.plan_code}
                        />
                      ))}
                    </Pie>
                  </PieChart>
                </ResponsiveContainer>
                <div className={styles.pieTotal} aria-hidden="true">
                  <strong>{numberFormatter.format(subscriptionTotal)}</strong>
                  <span>tenants</span>
                </div>
              </div>
              <ul className={styles.legend} aria-label="Subscription plans">
                {charts.subscription_distribution.map((item, index) => (
                  <li key={item.plan_code}>
                    <span
                      style={{
                        background: PIE_COLORS[index % PIE_COLORS.length],
                      }}
                      aria-hidden="true"
                    />
                    <div>
                      <strong>{item.plan_name}</strong>
                      <small>{item.plan_code}</small>
                    </div>
                    <b>{numberFormatter.format(item.tenant_count)}</b>
                  </li>
                ))}
              </ul>
            </div>
            <details className={styles.dataTable}>
              <summary>View subscription data</summary>
              <table>
                <thead>
                  <tr>
                    <th scope="col">Plan</th>
                    <th scope="col">Tenants</th>
                  </tr>
                </thead>
                <tbody>
                  {charts.subscription_distribution.map((item) => (
                    <tr key={item.plan_code}>
                      <td>{item.plan_name}</td>
                      <td>{numberFormatter.format(item.tenant_count)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </details>
          </>
        )}
      </article>
    </section>
  );
};
