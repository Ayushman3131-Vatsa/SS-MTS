import { ArrowLeft, Building2, Database, MapPin, PackageCheck, Users } from "lucide-react";
import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";

import { tenantsApi } from "../../features/tenant-management/api/tenants-api";
import type { TenantRecord } from "../../features/tenant-management/model/tenants";
import { Alert } from "../../shared/ui/Alert/Alert";
import styles from "./TenantDetailPage.module.css";

export const TenantDetailPage = () => {
  const { tenantId } = useParams();
  const [tenant, setTenant] = useState<TenantRecord | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!tenantId) {
      setError("Tenant identifier is missing.");
      return;
    }
    const controller = new AbortController();
    void tenantsApi
      .get(tenantId, controller.signal)
      .then(setTenant)
      .catch((requestError: unknown) => {
        if (requestError instanceof DOMException && requestError.name === "AbortError") {
          return;
        }
        setError("Tenant details could not be loaded.");
      });
    return () => controller.abort();
  }, [tenantId]);

  if (error) {
    return <div className={styles.page}><Alert tone="error" title="Tenant unavailable">{error}</Alert></div>;
  }
  if (!tenant) {
    return <div className={styles.page} role="status">Loading tenant details…</div>;
  }

  const address = [
    tenant.address_line_1,
    tenant.address_line_2,
    tenant.city,
    tenant.state_province,
    tenant.postal_code,
    tenant.country,
  ].filter(Boolean).join(", ");

  return (
    <div className={styles.page}>
      <Link className={styles.back} to="/platform/tenants">
        <ArrowLeft size={15} /> All tenants
      </Link>
      <header>
        <div>
          <p>{tenant.tenant_code}</p>
          <h1>{tenant.org_name}</h1>
          <span>{tenant.workspace_slug}</span>
        </div>
        <span className={styles.status}>{tenant.status}</span>
      </header>
      <div className={styles.summary}>
        <article><Building2 /><span><small>Plan</small><strong>{tenant.subscription_plan}</strong></span></article>
        <article><Database /><span><small>Database</small><strong>{tenant.database_mode} · {tenant.database_provisioning_state}</strong></span></article>
        <article><Users /><span><small>Users</small><strong>{tenant.user_count}</strong></span></article>
        <article><PackageCheck /><span><small>Offerings</small><strong>{tenant.offerings.length}</strong></span></article>
      </div>
      <div className={styles.grid}>
        <section>
          <h2>Company & contact</h2>
          <dl>
            <div><dt>Legal name</dt><dd>{tenant.legal_name || "—"}</dd></div>
            <div><dt>Industry</dt><dd>{tenant.industry || "—"}</dd></div>
            <div><dt>Company size</dt><dd>{tenant.company_size || "—"}</dd></div>
            <div><dt>Contact</dt><dd>{tenant.contact_name || "—"}</dd></div>
            <div><dt>Email</dt><dd>{tenant.contact_email || "—"}</dd></div>
            <div><dt>Phone</dt><dd>{tenant.contact_phone || "—"}</dd></div>
          </dl>
        </section>
        <section>
          <h2><MapPin size={17} /> Registered address</h2>
          <p>{address || "No address recorded."}</p>
          {tenant.website && <a href={tenant.website} target="_blank" rel="noreferrer">{tenant.website}</a>}
        </section>
        <section className={styles.offerings}>
          <h2>Licensed offerings</h2>
          <div>{tenant.offerings.map((offering) => <span key={offering.offering_id}>{offering.display_name}</span>)}</div>
        </section>
      </div>
    </div>
  );
};
