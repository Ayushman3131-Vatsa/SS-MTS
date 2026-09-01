import { Building2, ChevronLeft, ChevronRight, Eye, Plus, RefreshCw, Search } from "lucide-react";
import { useEffect, useState } from "react";
import { Link, useLocation } from "react-router-dom";

import { tenantsApi } from "../../features/tenant-management/api/tenants-api";
import type { TenantListResponse } from "../../features/tenant-management/model/tenants";
import { ApiError, InvalidApiResponseError, NetworkError } from "../../shared/api/errors";
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

const offeringSummary = (tenant: TenantListResponse["items"][number]) => {
  const now = Date.now();
  const effective = tenant.offerings.filter((offering) =>
    offering.status === "ACTIVE" &&
    new Date(offering.starts_at).getTime() <= now &&
    (offering.ends_at === null || new Date(offering.ends_at).getTime() > now),
  );
  const nextExpiry = tenant.offerings
    .map((offering) => offering.ends_at)
    .filter((value): value is string => value !== null && new Date(value).getTime() > now)
    .sort()[0];
  const expiryLabel = nextExpiry
    ? `next expiry ${dateFormatter.format(new Date(nextExpiry))}`
    : "no scheduled expiry";
  return `${effective.length}/${tenant.offerings.length} effective · ${expiryLabel}`;
};

export const AllTenantsPage = () => {
  const location = useLocation();
  const notice = (location.state as LocationState | null)?.notice;
  const [result, setResult] = useState<TenantListResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [query, setQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [page, setPage] = useState(1);
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    setError(null);
    setLoading(true);
    void tenantsApi
      .list({ page, pageSize: 25, query, status: statusFilter }, controller.signal)
      .then((payload) => {
        setResult(payload);
        setError(null);
      })
      .catch((requestError: unknown) => {
        if (requestError instanceof DOMException && requestError.name === "AbortError") {
          return;
        }
        if (requestError instanceof NetworkError) {
          setError("The tenant service could not be reached. Check that the API is running.");
        } else if (requestError instanceof ApiError) {
          setError(requestError.message);
        } else if (requestError instanceof InvalidApiResponseError) {
          setError("Tenant data was returned in an unexpected format.");
        } else {
          setError("Tenant data could not be loaded.");
        }
      })
      .finally(() => {
        if (!controller.signal.aborted) {
          setLoading(false);
        }
      });
    return () => controller.abort();
  }, [page, query, reloadKey, statusFilter]);

  return (
    <div className={styles.page}>
      <header className={styles.pageHeader}>
        <div>
          <h1>All Tenants</h1>
          <p>Review organizations and access plans.</p>
        </div>
        <Link className={styles.primaryLink} to="/platform/tenants/register">
          <Plus size={16} aria-hidden="true" />
          Register Tenant
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
          <select value={statusFilter} onChange={(event) => { setStatusFilter(event.target.value); setPage(1); }} aria-label="Filter tenants by status">
            <option value="">All statuses</option>
            <option value="ACTIVE">Active</option>
            <option value="SUSPENDED">Suspended</option>
          </select>
          <div>
            <span>
              {loading
                ? "Loading tenants…"
                : `${(result?.total ?? 0).toLocaleString()} tenants`}
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

        {loading ? (
          <div className={styles.loading} role="status">Loading tenant registry…</div>
        ) : error ? (
          <div className={styles.empty}>
            <h2>Could not load tenants</h2>
            <p>Use Refresh after the API is available, or register a tenant if this is a new environment.</p>
          </div>
        ) : result === null || result.items.length === 0 ? (
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
                {result.items.map((tenant) => (
                  <tr key={tenant.tenant_id}>
                    <td>
                      <strong>{tenant.org_name}</strong>
                      <span>{tenant.tenant_code}</span>
                    </td>
                    <td>
                      <span className={`${styles.badge} ${tenant.status === "ACTIVE" ? styles.active : styles.suspended}`}>
                        {tenant.status}
                      </span>
                    </td>
                    <td>
                      <strong>{tenant.subscription_plan}</strong>
                      <span>{offeringSummary(tenant)}</span>
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
            <div className={styles.pagination}>
              <span>Page {result.page} of {Math.max(1, Math.ceil(result.total / result.page_size))}</span>
              <div>
                <Button type="button" variant="secondary" disabled={page <= 1} onClick={() => setPage((value) => value - 1)}>
                  <ChevronLeft size={15} aria-hidden="true" /> Previous
                </Button>
                <Button type="button" variant="secondary" disabled={page >= Math.ceil(result.total / result.page_size)} onClick={() => setPage((value) => value + 1)}>
                  Next <ChevronRight size={15} aria-hidden="true" />
                </Button>
              </div>
            </div>
          </div>
        )}
      </section>
    </div>
  );
};
