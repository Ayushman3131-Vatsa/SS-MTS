import { Building2, Eye, Plus, RefreshCw, Search } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { Link, useLocation } from "react-router-dom";

import { tenantsApi } from "../../features/tenant-management/api/tenants-api";
import type { TenantRecord } from "../../features/tenant-management/model/tenants";
import { Alert } from "../../shared/ui/Alert/Alert";
import { Button } from "../../shared/ui/Button/Button";
import styles from "./AllTenantsPage.module.css";

const dateFormatter = new Intl.DateTimeFormat(undefined, {
  day: "numeric",
  month: "short",
  year: "numeric",
});

interface LocationState {
  notice?: string;
}

export const AllTenantsPage = () => {
  const location = useLocation();
  const notice = (location.state as LocationState | null)?.notice;
  const [tenants, setTenants] = useState<TenantRecord[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    setError(null);
    void tenantsApi
      .list(controller.signal)
      .then(setTenants)
      .catch((requestError: unknown) => {
        if (requestError instanceof DOMException && requestError.name === "AbortError") {
          return;
        }
        setError("Tenant data could not be loaded.");
      });
    return () => controller.abort();
  }, [reloadKey]);

  const filteredTenants = useMemo(() => {
    const normalized = query.trim().toLocaleLowerCase();
    if (!normalized) {
      return tenants ?? [];
    }
    return (tenants ?? []).filter((tenant) =>
      [tenant.org_name, tenant.tenant_code, tenant.workspace_slug]
        .join(" ")
        .toLocaleLowerCase()
        .includes(normalized),
    );
  }, [query, tenants]);

  return (
    <div className={styles.page}>
      <header className={styles.pageHeader}>
        <div>
          <p>Tenant administration</p>
          <h1>All tenants</h1>
          <span>Review organizations, access plans, databases, and user totals.</span>
        </div>
        <Link className={styles.primaryLink} to="/platform/tenants/register">
          <Plus size={16} aria-hidden="true" />
          Register tenant
        </Link>
      </header>

      {notice && (
        <Alert tone="success" title="Tenant registered">
          {notice}
        </Alert>
      )}
      {error && (
        <Alert tone="error" title="Tenant list unavailable">
          {error}
        </Alert>
      )}

      <section className={styles.tableCard}>
        <div className={styles.toolbar}>
          <label>
            <Search size={16} aria-hidden="true" />
            <input
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Search by tenant, code, or workspace"
              aria-label="Search tenants"
            />
          </label>
          <div>
            <span>
              {tenants === null
                ? "Loading tenants…"
                : `${filteredTenants.length} of ${tenants.length} tenants`}
            </span>
            <Button
              type="button"
              variant="secondary"
              onClick={() => setReloadKey((current) => current + 1)}
            >
              <RefreshCw size={15} aria-hidden="true" />
              Refresh
            </Button>
          </div>
        </div>

        {tenants === null ? (
          <div className={styles.loading} role="status">Loading tenant registry…</div>
        ) : tenants.length === 0 ? (
          <div className={styles.empty}>
            <span><Building2 size={23} aria-hidden="true" /></span>
            <h2>No tenants yet</h2>
            <p>Register the first organization to create its workspace and Tenant Admin.</p>
            <Link to="/platform/tenants/register">Register first tenant</Link>
          </div>
        ) : (
          <div className={styles.tableScroll}>
            <table>
              <thead>
                <tr>
                  <th>Tenant</th>
                  <th>Status</th>
                  <th>Plan</th>
                  <th>Database</th>
                  <th>Users</th>
                  <th>Created</th>
                  <th><span className={styles.visuallyHidden}>Actions</span></th>
                </tr>
              </thead>
              <tbody>
                {filteredTenants.map((tenant) => (
                  <tr key={tenant.tenant_id}>
                    <td>
                      <strong>{tenant.org_name}</strong>
                      <span>{tenant.tenant_code} · {tenant.workspace_slug}</span>
                    </td>
                    <td>
                      <span className={`${styles.badge} ${tenant.status === "ACTIVE" ? styles.active : styles.suspended}`}>
                        {tenant.status}
                      </span>
                    </td>
                    <td>
                      <strong>{tenant.subscription_plan}</strong>
                      <span>{tenant.offerings.length} licensed offerings</span>
                    </td>
                    <td>
                      <strong>{tenant.database_mode}</strong>
                      <span>{tenant.database_provisioning_state}</span>
                    </td>
                    <td>{tenant.user_count.toLocaleString()}</td>
                    <td>{dateFormatter.format(new Date(tenant.created_at))}</td>
                    <td>
                      <Link
                        className={styles.actionLink}
                        to={`/platform/tenants/${tenant.tenant_id}`}
                        aria-label={`View ${tenant.org_name}`}
                      >
                        <Eye size={15} aria-hidden="true" />
                        View
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            {filteredTenants.length === 0 && (
              <div className={styles.noResults}>No tenants match “{query}”.</div>
            )}
          </div>
        )}
      </section>
    </div>
  );
};
