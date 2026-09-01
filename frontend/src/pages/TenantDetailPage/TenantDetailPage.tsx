import { ArrowLeft, Building2, Check, Copy, Database, KeyRound, MapPin, PackageCheck, Pause, Play, Plus, RefreshCw, ShieldOff, Trash2, Users, X } from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";

import { tenantsApi } from "../../features/tenant-management/api/tenants-api";
import type { InitialTenantAdminCredentials, OfferingCatalogEntry, TenantFirstAccess, TenantOfferingEntitlement, TenantRecord } from "../../features/tenant-management/model/tenants";
import { TenantAdminCredentialsPanel } from "../../features/tenant-management/ui/TenantAdminCredentialsPanel/TenantAdminCredentialsPanel";
import { ApiError } from "../../shared/api/errors";
import { Alert } from "../../shared/ui/Alert/Alert";
import { Button } from "../../shared/ui/Button/Button";
import { ConfirmDialog } from "../../shared/ui/ConfirmDialog/ConfirmDialog";
import styles from "./TenantDetailPage.module.css";

const dateFormatter = new Intl.DateTimeFormat(undefined, {
  dateStyle: "medium",
  timeStyle: "short",
});

const toLocalInput = (date: Date) => {
  const offset = date.getTimezoneOffset();
  return new Date(date.getTime() - offset * 60_000).toISOString().slice(0, 16);
};

const formatDate = (value: string | null) => value ? dateFormatter.format(new Date(value)) : "No expiry";

const remainingTime = (endsAt: string | null) => {
  if (!endsAt) return "No expiry";
  const remainingMs = new Date(endsAt).getTime() - Date.now();
  if (remainingMs <= 0) return "Expired";
  const totalHours = Math.floor(remainingMs / (60 * 60 * 1000));
  const days = Math.floor(totalHours / 24);
  const hours = totalHours % 24;
  if (days > 0) return `${days}d ${hours}h remaining`;
  return `${Math.max(hours, 1)}h remaining`;
};

type PendingAction =
  | { type: "tenant"; action: "suspend" | "activate"; tenantName: string; version: number }
  | { type: "tenant-admin"; action: "enable" | "regenerate"; tenantName: string; email: string; version: number }
  | { type: "grant"; offeringId: string; offeringName: string; startsAt: string; endsAt: string; tenantVersion: number }
  | { type: "offering"; action: "suspend" | "resume" | "deactivate" | "remove"; entitlementId: string; offeringName: string; version: number };

type EntitlementTab = "active" | "suspended" | "deactivated";

const entitlementTabCopy: Record<EntitlementTab, { label: string; description: string }> = {
  active: { label: "Active", description: "Offerings the tenant can currently access." },
  suspended: { label: "Suspended", description: "Temporarily paused offerings that can be resumed." },
  deactivated: { label: "Deactivated", description: "Removed automatically 90 days after deactivation or expiry." },
};

const entitlementTabFor = (status: string): EntitlementTab => {
  if (status === "ACTIVE") return "active";
  if (status === "SUSPENDED") return "suspended";
  return "deactivated";
};

export const TenantDetailPage = () => {
  const { tenantId } = useParams();
  const [tenant, setTenant] = useState<TenantRecord | null>(null);
  const [catalog, setCatalog] = useState<OfferingCatalogEntry[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [selectedOffering, setSelectedOffering] = useState("");
  const [startsAt, setStartsAt] = useState(toLocalInput(new Date()));
  const [endsAt, setEndsAt] = useState(toLocalInput(new Date(Date.now() + 30 * 24 * 60 * 60 * 1000)));
  const [reason, setReason] = useState("");
  const [dialogReason, setDialogReason] = useState("");
  const [pendingAction, setPendingAction] = useState<PendingAction | null>(null);
  const [entitlementTab, setEntitlementTab] = useState<EntitlementTab>("active");
  const [credentials, setCredentials] = useState<InitialTenantAdminCredentials | null>(null);
  const [copiedCredential, setCopiedCredential] = useState<string | null>(null);
  const [rotatedAccess, setRotatedAccess] = useState<TenantFirstAccess | null>(null);

  const load = useCallback(async () => {
    if (!tenantId) {
      setError("Tenant identifier is missing.");
      return;
    }
    const [tenantResult, catalogResult] = await Promise.all([
      tenantsApi.get(tenantId),
      tenantsApi.catalog(),
    ]);
    setTenant(tenantResult);
    setCatalog(catalogResult);
  }, [tenantId]);

  useEffect(() => {
    void load().catch((requestError: unknown) => {
      if (requestError instanceof DOMException && requestError.name === "AbortError") return;
      setError("Tenant details could not be loaded.");
    });
  }, [load]);

  const currentEntitlements = useMemo(
    () => (tenant?.offerings ?? []).filter((item) => ["ACTIVE", "SUSPENDED"].includes(item.status)),
    [tenant],
  );
  const openEntitlements = useMemo(
    () => new Set(currentEntitlements.map((item) => item.offering_id)),
    [currentEntitlements],
  );
  const entitlementsByTab = useMemo<Record<EntitlementTab, TenantOfferingEntitlement[]>>(() => ({
    active: (tenant?.offerings ?? []).filter((item) => entitlementTabFor(item.status) === "active"),
    suspended: (tenant?.offerings ?? []).filter((item) => entitlementTabFor(item.status) === "suspended"),
    deactivated: (tenant?.offerings ?? []).filter((item) => entitlementTabFor(item.status) === "deactivated"),
  }), [tenant]);
  const visibleEntitlements = entitlementsByTab[entitlementTab];
  const availableOfferings = catalog.filter((offering) => offering.status === "ACTIVE" && !openEntitlements.has(offering.offering_id));

  const reloadAfter = async (operation: string, callback: () => Promise<unknown>): Promise<boolean> => {
    setBusy(operation);
    setError(null);
    try {
      await callback();
      await load();
      return true;
    } catch (requestError) {
      if (requestError instanceof ApiError && requestError.status === 409) {
        setError("This record changed in another session. The latest data has been loaded; retry the action.");
      } else if (requestError instanceof ApiError) {
        setError(requestError.message);
      } else {
        setError("The tenant operation could not be completed.");
      }
      return false;
    } finally {
      setBusy(null);
    }
  };

  const handleTenantAction = (action: "suspend" | "activate") => {
    if (!tenantId || !tenant) return;
    setDialogReason(reason);
    setPendingAction({ type: "tenant", action, tenantName: tenant.org_name, version: tenant.version });
  };

  const handleTenantAdminAction = (action: "enable" | "regenerate") => {
    if (!tenant) return;
    setPendingAction({
      type: "tenant-admin",
      action,
      tenantName: tenant.org_name,
      email: tenant.contact_email ?? "the primary contact email",
      version: tenant.version,
    });
  };

  const handleGrant = () => {
    if (!tenantId || !selectedOffering) {
      setError("Select an offering before granting access.");
      return;
    }
    const start = new Date(startsAt);
    const end = new Date(endsAt);
    if (!Number.isFinite(start.getTime()) || !Number.isFinite(end.getTime()) || end <= start) {
      setError("The offering end date must be later than its start date.");
      return;
    }
    const offering = catalog.find((item) => item.offering_id === selectedOffering);
    if (!offering || !tenant) {
      setError("The selected offering is no longer available. Refresh and try again.");
      return;
    }
    setDialogReason(reason);
    setPendingAction({
      type: "grant",
      offeringId: selectedOffering,
      offeringName: offering.display_name,
      startsAt: start.toISOString(),
      endsAt: end.toISOString(),
      tenantVersion: tenant.version,
    });
  };

  const prepareRegrant = (entitlement: TenantOfferingEntitlement) => {
    setSelectedOffering(entitlement.offering_id);
    const start = new Date();
    setStartsAt(toLocalInput(start));
    setEndsAt(toLocalInput(new Date(start.getTime() + 30 * 24 * 60 * 60 * 1000)));
    window.scrollTo({ top: 0, behavior: "smooth" });
  };

  const handleOfferingAction = (entitlement: TenantOfferingEntitlement, action: "suspend" | "resume" | "deactivate" | "remove") => {
    if (!tenantId) return;
    setDialogReason(["deactivate", "remove"].includes(action) ? "" : reason);
    setPendingAction({
      type: "offering",
      action,
      entitlementId: entitlement.entitlement_id,
      offeringName: entitlement.display_name,
      version: entitlement.version,
    });
  };

  const executePendingAction = async () => {
    if (!pendingAction || !tenantId) return;
    let succeeded = false;
    let issuedCredentials: InitialTenantAdminCredentials | null = null;
    if (pendingAction.type === "tenant") {
      succeeded = await reloadAfter(`tenant-${pendingAction.action}`, () => tenantsApi.tenantAction(tenantId, pendingAction.action, {
        expected_version: pendingAction.version,
        reason: dialogReason || null,
      }));
    } else if (pendingAction.type === "tenant-admin") {
      succeeded = await reloadAfter(`tenant-admin-${pendingAction.action}`, async () => {
        issuedCredentials = pendingAction.action === "enable"
          ? await tenantsApi.enable(tenantId, { expected_version: pendingAction.version })
          : await tenantsApi.regenerateInitialPassword(tenantId, { expected_version: pendingAction.version });
      });
      if (issuedCredentials) {
        setCredentials(issuedCredentials);
        setCopiedCredential(null);
      }
    } else if (pendingAction.type === "grant") {
      succeeded = await reloadAfter("grant-offering", () => tenantsApi.grant(tenantId, {
        offering_id: pendingAction.offeringId,
        starts_at: pendingAction.startsAt,
        ends_at: pendingAction.endsAt,
        expected_tenant_version: pendingAction.tenantVersion,
        reason: dialogReason || null,
      }));
    } else if (pendingAction.action === "remove") {
      succeeded = await reloadAfter(`offering-remove-${pendingAction.entitlementId}`, () => tenantsApi.removeEntitlement(
        tenantId,
        pendingAction.entitlementId,
        { expected_version: pendingAction.version, reason: dialogReason },
      ));
    } else {
      const transitionAction = pendingAction.action;
      succeeded = await reloadAfter(`offering-${pendingAction.action}-${pendingAction.entitlementId}`, () => tenantsApi.offeringAction(
        tenantId,
        pendingAction.entitlementId,
        transitionAction,
        { expected_version: pendingAction.version, reason: dialogReason || null },
      ));
    }
    if (pendingAction.type === "tenant-admin" && issuedCredentials) {
      setPendingAction(null);
      setDialogReason("");
      return;
    }
    if (succeeded) {
      if (pendingAction.type === "grant" || (pendingAction.type === "offering" && pendingAction.action === "resume")) {
        setEntitlementTab("active");
      } else if (pendingAction.type === "offering" && pendingAction.action === "suspend") {
        setEntitlementTab("suspended");
      } else if (pendingAction.type === "offering" && ["deactivate", "remove"].includes(pendingAction.action)) {
        setEntitlementTab("deactivated");
      }
      setPendingAction(null);
      setDialogReason("");
    }
  };

  const copyCredential = async (label: string, value: string) => {
    try {
      if (navigator.clipboard?.writeText) {
        await navigator.clipboard.writeText(value);
      } else {
        const temporaryField = document.createElement("textarea");
        temporaryField.value = value;
        temporaryField.style.position = "fixed";
        temporaryField.style.opacity = "0";
        document.body.append(temporaryField);
        temporaryField.select();
        const copied = document.execCommand("copy");
        temporaryField.remove();
        if (!copied) throw new Error("Copy command was rejected");
      }
      setCopiedCredential(label);
    } catch {
      setError("Credentials could not be copied. Select and copy the value manually.");
    }
  };

  const handleRotateFirstAccess = async () => {
    if (!tenantId) return;
    const succeeded = await reloadAfter("rotate-first-access", async () => {
      const access = await tenantsApi.rotateFirstAccess(tenantId);
      setRotatedAccess(access);
    });
    if (!succeeded) {
      setRotatedAccess(null);
    }
  };

  if (error && !tenant) {
    return <div className={styles.page}><Alert tone="error" title="Tenant unavailable">{error}</Alert></div>;
  }
  if (!tenant) {
    return <div className={styles.page} role="status">Loading tenant details…</div>;
  }

  const address = [tenant.address_line_1, tenant.address_line_2, tenant.city, tenant.state_province, tenant.postal_code, tenant.country].filter(Boolean).join(", ");

  return (
    <div className={styles.page}>
      <Link className={styles.back} to="/platform/tenants"><ArrowLeft size={15} /> All tenants</Link>
      <header>
        <div>
          <p>{tenant.tenant_code}</p>
          <h1>{tenant.org_name}</h1>
        </div>
        <div className={styles.headerActions}>
          <span className={`${styles.status} ${tenant.status === "ACTIVE" ? styles.active : styles.suspended}`}>{tenant.status}</span>
          {tenant.tenant_admin_provisioning_status === "NOT_ENABLED" && (
            <Button variant="secondary" disabled={Boolean(busy)} onClick={() => handleTenantAdminAction("enable")}>
              <KeyRound size={15} /> Enable Tenant
            </Button>
          )}
          {tenant.tenant_admin_provisioning_status === "PENDING_PASSWORD_CHANGE" && (
            <Button variant="secondary" disabled={Boolean(busy)} onClick={() => handleTenantAdminAction("regenerate")}>
              <RefreshCw size={15} /> Regenerate temporary password
            </Button>
          )}
          <Button variant="secondary" disabled={Boolean(busy)} onClick={() => handleTenantAction(tenant.status === "ACTIVE" ? "suspend" : "activate")}>
            {tenant.status === "ACTIVE" ? <Pause size={15} /> : <Play size={15} />}
            {tenant.status === "ACTIVE" ? "Suspend tenant" : "Activate tenant"}
          </Button>
        </div>
      </header>
      {error && <Alert tone="error" title="Operation unavailable">{error}</Alert>}
      <section className={styles.accessPanel}>
        <div className={styles.accessHeader}>
          <div>
            <h2>Admin access</h2>
            <p>Issue a new temporary password if the tenant admin has not completed first sign-in.</p>
          </div>
          <Button
            type="button"
            variant="secondary"
            loading={busy === "rotate-first-access"}
            loadingLabel="Resetting…"
            onClick={() => void handleRotateFirstAccess()}
          >
            <KeyRound size={15} aria-hidden="true" />
            Reset password
          </Button>
        </div>
        {rotatedAccess && (
          <div className={styles.accessCredentials}>
            <p className={styles.accessCredentialsLabel}>New credentials</p>
            <TenantAdminCredentialsPanel access={rotatedAccess} />
          </div>
        )}
      </section>
      <div className={styles.summary}>
        <article><Building2 /><span><small>Plan</small><strong>{tenant.subscription_plan}</strong></span></article>
        <article><Database /><span><small>Database</small><strong>{tenant.database_mode} · {tenant.database_provisioning_state}</strong></span></article>
        <article><Users /><span><small>Users</small><strong>{tenant.user_count}</strong></span></article>
        <article><PackageCheck /><span><small>Current entitlements</small><strong>{currentEntitlements.length}</strong></span></article>
      </div>
      <div className={styles.grid}>
        <section>
          <h2>Company & contact</h2>
          <dl>
            <div><dt>Legal name</dt><dd>{tenant.legal_name || "—"}</dd></div>
            <div><dt>Industry</dt><dd>{tenant.industry || "—"}</dd></div>
            <div><dt>Company size</dt><dd>{tenant.company_size || "—"}</dd></div>
            <div><dt>Contact</dt><dd>{tenant.contact_name || "—"}</dd></div>
            <div><dt>Designation</dt><dd>{tenant.contact_designation || "—"}</dd></div>
            <div><dt>Email</dt><dd>{tenant.contact_email || "—"}</dd></div>
            <div><dt>Phone</dt><dd>{tenant.contact_phone || "—"}</dd></div>
            {tenant.alternate_contact_name && (
              <div><dt>Alternate contact</dt><dd>{tenant.alternate_contact_name}</dd></div>
            )}
            {tenant.alternate_contact_designation && (
              <div><dt>Alternate designation</dt><dd>{tenant.alternate_contact_designation}</dd></div>
            )}
            {tenant.alternate_contact_email && (
              <div><dt>Alternate email</dt><dd>{tenant.alternate_contact_email}</dd></div>
            )}
            {tenant.alternate_contact_phone && (
              <div><dt>Alternate phone</dt><dd>{tenant.alternate_contact_phone}</dd></div>
            )}
          </dl>
        </section>
        <section>
          <h2><MapPin size={17} /> Registered address</h2>
          <p>{address || "No address recorded."}</p>
          {tenant.website && <a href={tenant.website} target="_blank" rel="noreferrer">{tenant.website}</a>}
        </section>
        <section className={styles.offerings}>
          <div className={styles.sectionHeading}>
            <div>
              <h2>Offering entitlements</h2>
              <p>Manage time-bound access to workspace products.</p>
            </div>
            <span className={styles.currentCount}>{currentEntitlements.length} current</span>
          </div>

          <div className={styles.grantPanel}>
            <div className={styles.grantIntro}>
              <span className={styles.grantIcon} aria-hidden="true"><Plus size={17} /></span>
              <div>
                <h3>Grant an offering</h3>
                <p>Choose a start and required expiry date. Times are entered in your local timezone.</p>
              </div>
            </div>
            <form className={styles.grantForm} onSubmit={(event) => { event.preventDefault(); handleGrant(); }}>
              <label className={styles.offeringField}>
                <span>Offering</span>
                <select required value={selectedOffering} onChange={(event) => setSelectedOffering(event.target.value)}>
                  <option value="">{availableOfferings.length > 0 ? "Select an active offering" : "No offerings available to grant"}</option>
                  {availableOfferings.map((offering) => <option key={offering.offering_id} value={offering.offering_id}>{offering.display_name}</option>)}
                </select>
              </label>
              <label>
                <span>Starts</span>
                <input required type="datetime-local" value={startsAt} onChange={(event) => setStartsAt(event.target.value)} />
              </label>
              <label>
                <span>Expires</span>
                <input required type="datetime-local" min={startsAt} value={endsAt} onChange={(event) => setEndsAt(event.target.value)} />
              </label>
              <label className={styles.reasonField}>
                <span>Internal note <small>Optional</small></span>
                <input value={reason} onChange={(event) => setReason(event.target.value)} placeholder="Why is access being granted?" />
              </label>
              <Button type="submit" disabled={availableOfferings.length === 0} loading={busy === "grant-offering"}><Plus size={15} /> Grant offering</Button>
            </form>
          </div>

          <div className={styles.tabBar} role="tablist" aria-label="Offering entitlement status">
            {(Object.keys(entitlementTabCopy) as EntitlementTab[]).map((tab) => (
              <button
                key={tab}
                type="button"
                role="tab"
                id={`entitlement-tab-${tab}`}
                aria-controls={`entitlement-panel-${tab}`}
                aria-selected={entitlementTab === tab}
                className={entitlementTab === tab ? styles.selectedTab : ""}
                onClick={() => setEntitlementTab(tab)}
              >
                <span>{entitlementTabCopy[tab].label}</span>
                <strong>{entitlementsByTab[tab].length}</strong>
              </button>
            ))}
          </div>

          <div
            className={styles.entitlementPanel}
            role="tabpanel"
            id={`entitlement-panel-${entitlementTab}`}
            aria-labelledby={`entitlement-tab-${entitlementTab}`}
          >
            <div className={styles.listHeading}>
              <div>
                <h3>{entitlementTabCopy[entitlementTab].label} offerings</h3>
                <p>{entitlementTabCopy[entitlementTab].description}</p>
              </div>
              <span>{visibleEntitlements.length} {visibleEntitlements.length === 1 ? "offering" : "offerings"}</span>
            </div>

            <div className={styles.entitlementList}>
              {visibleEntitlements.length === 0 ? (
                <div className={styles.emptyState}>
                  <PackageCheck size={24} aria-hidden="true" />
                  <h4>No {entitlementTabCopy[entitlementTab].label.toLowerCase()} offerings</h4>
                  <p>Entitlements in this state will appear here.</p>
                </div>
              ) : visibleEntitlements.map((entitlement) => {
                const isLegacyUnlimited = ["ACTIVE", "SUSPENDED"].includes(entitlement.status) && !entitlement.ends_at;
                return (
                  <article className={styles.entitlementCard} key={entitlement.entitlement_id}>
                    <div className={styles.entitlementIdentity}>
                      <div>
                        <strong>{entitlement.display_name}</strong>
                        <span>{entitlement.code} · Version {entitlement.version}</span>
                      </div>
                      <span className={`${styles.badge} ${styles[entitlement.status.toLowerCase()] ?? ""}`}>{entitlement.status}</span>
                    </div>

                    <dl className={styles.entitlementMeta}>
                      <div><dt>Starts</dt><dd>{formatDate(entitlement.starts_at)}</dd></div>
                      <div><dt>Expires</dt><dd className={isLegacyUnlimited ? styles.legacyExpiry : ""}>{isLegacyUnlimited ? "Legacy: no expiry" : formatDate(entitlement.ends_at)}</dd></div>
                      <div><dt>Remaining</dt><dd>{isLegacyUnlimited ? "Unlimited (legacy)" : remainingTime(entitlement.ends_at)}</dd></div>
                      {entitlement.reason && <div className={styles.reasonMeta}><dt>Reason</dt><dd>{entitlement.reason}</dd></div>}
                    </dl>

                    <div className={styles.entitlementActions}>
                      {entitlement.status === "ACTIVE" && <Button variant="secondary" disabled={Boolean(busy)} onClick={() => handleOfferingAction(entitlement, "suspend")}><Pause size={14} /> Suspend</Button>}
                      {entitlement.status === "SUSPENDED" && <Button variant="secondary" disabled={Boolean(busy)} onClick={() => handleOfferingAction(entitlement, "resume")}><Play size={14} /> Resume</Button>}
                      {["ACTIVE", "SUSPENDED"].includes(entitlement.status) && <Button variant="secondary" disabled={Boolean(busy)} onClick={() => handleOfferingAction(entitlement, "deactivate")}><ShieldOff size={14} /> Deactivate</Button>}
                      {["EXPIRED", "DEACTIVATED"].includes(entitlement.status) && catalog.some((item) => item.offering_id === entitlement.offering_id && item.status === "ACTIVE") && <Button variant="secondary" disabled={Boolean(busy)} onClick={() => prepareRegrant(entitlement)}><Plus size={14} /> Re-grant</Button>}
                      {["EXPIRED", "DEACTIVATED"].includes(entitlement.status) && <Button className={styles.removeButton} variant="secondary" disabled={Boolean(busy)} onClick={() => handleOfferingAction(entitlement, "remove")}><Trash2 size={14} /> Remove</Button>}
                    </div>
                  </article>
                );
              })}
            </div>
          </div>
        </section>
      </div>
      <ConfirmDialog
        open={Boolean(pendingAction)}
        title={pendingAction?.type === "grant"
          ? `Grant ${pendingAction.offeringName}?`
          : pendingAction?.type === "tenant"
            ? `${pendingAction.action === "suspend" ? "Suspend" : "Activate"} tenant?`
            : pendingAction?.type === "tenant-admin"
              ? pendingAction.action === "enable" ? "Enable tenant?" : "Regenerate temporary password?"
            : `${pendingAction?.action === "remove" ? "Remove" : pendingAction?.action === "deactivate" ? "Deactivate" : pendingAction?.action === "resume" ? "Resume" : "Suspend"} offering?`}
        description={pendingAction?.type === "grant"
          ? `${pendingAction.offeringName} will be available from ${formatDate(pendingAction.startsAt)} until ${formatDate(pendingAction.endsAt)}.`
          : pendingAction?.type === "tenant"
            ? `You are about to ${pendingAction.action} ${pendingAction.tenantName}. This changes access for the tenant.`
            : pendingAction?.type === "tenant-admin"
              ? pendingAction.action === "enable"
                ? <>This creates the first Tenant Admin for {pendingAction.tenantName} using&nbsp;<strong className={styles.primaryContactEmail}>{pendingAction.email}</strong>. The generated password will be shown only once.</>
                : `This replaces the temporary password for ${pendingAction.email}. Any prior temporary password will stop working.`
            : pendingAction?.action === "remove"
              ? `${pendingAction.offeringName} and its entitlement history will be permanently deleted. This cannot be undone.`
              : `You are about to ${pendingAction?.action} ${pendingAction?.offeringName}. Entitlement dates will not be extended.`}
        confirmLabel={pendingAction?.type === "tenant"
          ? pendingAction.action === "suspend" ? "Suspend tenant" : "Activate tenant"
          : pendingAction?.type === "tenant-admin"
            ? pendingAction.action === "enable" ? "Enable tenant" : "Regenerate password"
          : pendingAction?.type === "grant" ? "Grant offering"
          : pendingAction?.action === "remove" ? "Remove permanently"
          : pendingAction?.action === "deactivate" ? "Deactivate offering" : `${pendingAction?.action === "resume" ? "Resume" : "Suspend"} offering`}
        destructive={pendingAction?.type === "tenant" ? pendingAction.action === "suspend" : pendingAction?.type === "offering" && ["deactivate", "remove"].includes(pendingAction.action)}
        reason={dialogReason}
        reasonLabel={pendingAction?.type === "offering" && pendingAction.action === "remove" ? "Reason for permanent removal" : pendingAction?.type === "offering" && pendingAction.action === "deactivate" ? "Reason for deactivation" : "Reason (optional)"}
        reasonRequired={pendingAction?.type === "offering" && ["deactivate", "remove"].includes(pendingAction.action)}
        busy={Boolean(busy)}
        onReasonChange={pendingAction?.type === "tenant-admin" ? undefined : setDialogReason}
        onCancel={() => { if (!busy) { setPendingAction(null); setDialogReason(""); } }}
        onConfirm={() => void executePendingAction()}
      />
      {credentials && (
        <div className={styles.credentialsBackdrop} role="presentation">
          <section className={styles.credentialsDialog} role="dialog" aria-modal="true" aria-labelledby="tenant-credentials-title" aria-describedby="tenant-credentials-description">
            <div className={styles.credentialsHeader}>
              <span className={styles.credentialsIcon} aria-hidden="true"><KeyRound size={19} /></span>
              <button className={styles.closeCredentials} type="button" onClick={() => setCredentials(null)} aria-label="Close credentials dialog"><X size={18} /></button>
            </div>
            <h2 id="tenant-credentials-title">Tenant login credentials</h2>
            <p id="tenant-credentials-description">Copy these credentials now. The password is shown only once and the tenant will be required to change it at first sign-in.</p>
            <div className={styles.credentialFields}>
              <label><span>Email</span><div><output>{credentials.email}</output><Button type="button" variant="secondary" onClick={() => void copyCredential("email", credentials.email)}>{copiedCredential === "email" ? <Check size={15} /> : <Copy size={15} />}{copiedCredential === "email" ? "Copied" : "Copy"}</Button></div></label>
              <label><span>Temporary password</span><div><output>{credentials.temporary_password}</output><Button type="button" variant="secondary" onClick={() => void copyCredential("password", credentials.temporary_password)}>{copiedCredential === "password" ? <Check size={15} /> : <Copy size={15} />}{copiedCredential === "password" ? "Copied" : "Copy"}</Button></div></label>
            </div>
            <div className={styles.credentialActions}>
              <Button type="button" variant="secondary" onClick={() => void copyCredential("credentials", `Email: ${credentials.email}\nTemporary password: ${credentials.temporary_password}`)}>{copiedCredential === "credentials" ? <Check size={15} /> : <Copy size={15} />}{copiedCredential === "credentials" ? "Credentials copied" : "Copy credentials"}</Button>
              <Button type="button" onClick={() => setCredentials(null)}>I have copied them</Button>
            </div>
          </section>
        </div>
      )}
    </div>
  );
};
