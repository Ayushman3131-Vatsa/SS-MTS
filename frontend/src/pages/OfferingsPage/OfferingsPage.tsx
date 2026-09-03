import { BadgeDollarSign, BookOpen, Boxes, BriefcaseBusiness, Building2, CalendarDays, ChartNoAxesCombined, ChartPie, ChartSpline, ClipboardCheck, Clock, Cloud, Database, GraduationCap, Headphones, HeartPulse, KanbanSquare, Landmark, Laptop, Library, MapPin, MessagesSquare, Monitor, Package, Pencil, PhoneCall, Plus, Power, ReceiptText, RefreshCw, School, Search, ShieldCheck, ShoppingCart, Smartphone, Stethoscope, TicketCheck, Trash2, Truck, UserCog, UserRound, UserSearch, Users, WalletCards, Workflow, Wrench, X } from "lucide-react";
import { type FormEvent, useEffect, useRef, useState } from "react";

import { offeringsApi } from "../../features/offering-management/api/offerings-api";
import type { OfferingCatalogItem, OfferingCreatePayload, OfferingRoleType } from "../../features/offering-management/model/offerings";
import { Alert } from "../../shared/ui/Alert/Alert";
import { Button } from "../../shared/ui/Button/Button";
import { ConfirmDialog } from "../../shared/ui/ConfirmDialog/ConfirmDialog";
import styles from "./OfferingsPage.module.css";

type EditorValues = Omit<OfferingCreatePayload, "route_slug" | "role_type"> & {
  role_type: OfferingRoleType | "";
};

const iconOptions = [
  { key: "users", label: "People", category: "People", Icon: Users },
  { key: "user-round", label: "Employee", category: "People", Icon: UserRound },
  { key: "user-cog", label: "Administration", category: "People", Icon: UserCog },
  { key: "user-search", label: "Recruiting", category: "People", Icon: UserSearch },
  { key: "graduation-cap", label: "Learning", category: "People", Icon: GraduationCap },
  { key: "heart-pulse", label: "Wellbeing", category: "People", Icon: HeartPulse },
  { key: "clipboard-check", label: "Tasks", category: "Work", Icon: ClipboardCheck },
  { key: "kanban-square", label: "Projects", category: "Work", Icon: KanbanSquare },
  { key: "calendar-days", label: "Calendar", category: "Work", Icon: CalendarDays },
  { key: "clock", label: "Time", category: "Work", Icon: Clock },
  { key: "briefcase-business", label: "Management", category: "Work", Icon: BriefcaseBusiness },
  { key: "workflow", label: "Workflow", category: "Work", Icon: Workflow },
  { key: "school", label: "School", category: "Industry", Icon: School },
  { key: "building-2", label: "Business", category: "Industry", Icon: Building2 },
  { key: "stethoscope", label: "Healthcare", category: "Industry", Icon: Stethoscope },
  { key: "shopping-cart", label: "Commerce", category: "Industry", Icon: ShoppingCart },
  { key: "truck", label: "Logistics", category: "Industry", Icon: Truck },
  { key: "map-pin", label: "Location", category: "Industry", Icon: MapPin },
  { key: "wallet-cards", label: "Payroll", category: "Finance", Icon: WalletCards },
  { key: "landmark", label: "Banking", category: "Finance", Icon: Landmark },
  { key: "receipt-text", label: "Billing", category: "Finance", Icon: ReceiptText },
  { key: "badge-dollar-sign", label: "Payments", category: "Finance", Icon: BadgeDollarSign },
  { key: "chart-no-axes-combined", label: "Reports", category: "Finance", Icon: ChartNoAxesCombined },
  { key: "chart-pie", label: "Analytics", category: "Finance", Icon: ChartPie },
  { key: "headphones", label: "Support", category: "Service", Icon: Headphones },
  { key: "messages-square", label: "Messaging", category: "Service", Icon: MessagesSquare },
  { key: "ticket-check", label: "Help desk", category: "Service", Icon: TicketCheck },
  { key: "phone-call", label: "Contact centre", category: "Service", Icon: PhoneCall },
  { key: "book-open", label: "Knowledge", category: "Service", Icon: BookOpen },
  { key: "library", label: "Library", category: "Service", Icon: Library },
  { key: "monitor", label: "Assets", category: "Technology", Icon: Monitor },
  { key: "laptop", label: "Devices", category: "Technology", Icon: Laptop },
  { key: "smartphone", label: "Mobile", category: "Technology", Icon: Smartphone },
  { key: "cloud", label: "Cloud", category: "Technology", Icon: Cloud },
  { key: "database", label: "Data", category: "Technology", Icon: Database },
  { key: "shield-check", label: "Security", category: "Technology", Icon: ShieldCheck },
  { key: "boxes", label: "Inventory", category: "Technology", Icon: Boxes },
  { key: "wrench", label: "Tools", category: "Technology", Icon: Wrench },
  { key: "package", label: "Other", category: "Technology", Icon: Package },
  { key: "chart-spline", label: "Performance", category: "Technology", Icon: ChartSpline },
] as const;

const iconCategories = ["All", "People", "Work", "Industry", "Finance", "Service", "Technology"] as const;

const toRouteSlug = (displayName: string) => displayName
  .toLowerCase()
  .trim()
  .replace(/[^a-z0-9]+/g, "-")
  .replace(/^-+|-+$/g, "")
  .slice(0, 63);

const blankEditor = (): EditorValues => ({
  code: "",
  display_name: "",
  description: "",
  icon_key: "package",
  sort_order: 0,
  status: "INACTIVE",
  role_type: "",
});

const valuesFor = (offering: OfferingCatalogItem): EditorValues => ({
  code: offering.code,
  display_name: offering.display_name,
  description: offering.description,
  icon_key: offering.icon_key,
  sort_order: offering.sort_order,
  status: offering.status,
  role_type: offering.role_type ?? "TENANT",
});

const roleTypeLabels: Record<OfferingRoleType, string> = {
  PLATFORM: "Platform",
  TENANT: "Tenant",
  BOTH: "Platform / Tenant",
};

export const OfferingsPage = () => {
  const [offerings, setOfferings] = useState<OfferingCatalogItem[] | null>(null);
  const [query, setQuery] = useState("");
  const [debouncedQuery, setDebouncedQuery] = useState("");
  const [roleTypeFilter, setRoleTypeFilter] = useState<"" | OfferingRoleType>("");
  const [statusFilter, setStatusFilter] = useState<"" | "ACTIVE" | "INACTIVE">("");
  const [refreshVersion, setRefreshVersion] = useState(0);
  const [editor, setEditor] = useState<EditorValues>(blankEditor);
  const [editorOpen, setEditorOpen] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [iconPickerOpen, setIconPickerOpen] = useState(false);
  const [iconCategory, setIconCategory] = useState<(typeof iconCategories)[number]>("All");
  const [iconQuery, setIconQuery] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [pendingAction, setPendingAction] = useState<OfferingCatalogItem | null>(null);
  const [pendingDelete, setPendingDelete] = useState<OfferingCatalogItem | null>(null);
  const [deleteReason, setDeleteReason] = useState("");
  const [actionBusy, setActionBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const editorTitleRef = useRef<HTMLHeadingElement>(null);

  useEffect(() => {
    const timer = window.setTimeout(() => setDebouncedQuery(query.trim()), 300);
    return () => window.clearTimeout(timer);
  }, [query]);

  useEffect(() => {
    const controller = new AbortController();
    setError(null);
    setOfferings(null);
    void offeringsApi.list(controller.signal, {
      query: debouncedQuery || undefined,
      roleType: roleTypeFilter || undefined,
      status: statusFilter || undefined,
    }).then(setOfferings).catch((requestError: unknown) => {
      if (requestError instanceof DOMException && requestError.name === "AbortError") return;
      setError("Offering catalog data could not be loaded.");
      setOfferings([]);
    });
    return () => controller.abort();
  }, [debouncedQuery, refreshVersion, roleTypeFilter, statusFilter]);

  useEffect(() => {
    if (!editorOpen) return;
    editorTitleRef.current?.focus({ preventScroll: true });
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape" && !submitting) closeEditor();
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [editorOpen, submitting]);

  const updateEditor = <K extends keyof EditorValues>(field: K, value: EditorValues[K]) => {
    setEditor((current) => ({ ...current, [field]: value }));
  };

  const visibleIcons = iconOptions.filter((icon) => {
    const matchesCategory = iconCategory === "All" || icon.category === iconCategory;
    const search = iconQuery.trim().toLowerCase();
    return matchesCategory && (!search || `${icon.label} ${icon.key}`.toLowerCase().includes(search));
  });
  const SelectedIcon = iconOptions.find((icon) => icon.key === editor.icon_key)?.Icon ?? Package;

  const closeEditor = () => {
    setEditorOpen(false);
    setEditor(blankEditor());
    setEditingId(null);
    setIconPickerOpen(false);
    setIconCategory("All");
    setIconQuery("");
  };

  const openCreate = () => {
    setError(null);
    closeEditor();
    setEditorOpen(true);
  };

  const openEdit = (offering: OfferingCatalogItem) => {
    setError(null);
    setEditor(valuesFor(offering));
    setEditingId(offering.offering_id);
    setIconPickerOpen(false);
    setIconCategory("All");
    setIconQuery("");
    setEditorOpen(true);
  };

  const submitEditor = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!editor.role_type) {
      setError("Select whether this offering is for Platform, Tenant, or Platform / Tenant.");
      return;
    }
    setSubmitting(true);
    setError(null);
    try {
      const result = editingId
        ? await offeringsApi.update(editingId, {
          display_name: editor.display_name,
          description: editor.description,
          icon_key: editor.icon_key,
          sort_order: editor.sort_order,
          role_type: editor.role_type,
        })
        : await offeringsApi.create({
          ...editor,
          role_type: editor.role_type,
          route_slug: toRouteSlug(editor.display_name),
        });
      setNotice(editingId ? `${result.display_name} updated.` : `${result.display_name} created.`);
      closeEditor();
      setRefreshVersion((current) => current + 1);
    } catch (requestError: unknown) {
      setError(requestError instanceof Error ? requestError.message : "The offering could not be saved.");
    } finally {
      setSubmitting(false);
    }
  };

  const confirmStatus = async () => {
    if (!pendingAction) return;
    setActionBusy(true);
    setError(null);
    try {
      const nextStatus = pendingAction.status === "ACTIVE" ? "INACTIVE" : "ACTIVE";
      const result = await offeringsApi.setStatus(pendingAction.offering_id, nextStatus);
      setNotice(`${result.display_name} is now ${result.status.toLowerCase()}.`);
      setPendingAction(null);
      setRefreshVersion((current) => current + 1);
    } catch (requestError: unknown) {
      setError(requestError instanceof Error ? requestError.message : "The offering status could not be changed.");
    } finally {
      setActionBusy(false);
    }
  };

  const confirmDelete = async () => {
    if (!pendingDelete) return;
    setActionBusy(true);
    setError(null);
    try {
      await offeringsApi.remove(pendingDelete.offering_id, deleteReason);
      setNotice(`${pendingDelete.display_name} deleted.`);
      setPendingDelete(null);
      setDeleteReason("");
      setRefreshVersion((current) => current + 1);
    } catch (requestError: unknown) {
      setError(requestError instanceof Error ? requestError.message : "The offering could not be deleted.");
    } finally {
      setActionBusy(false);
    }
  };

  return (
    <div className={styles.page}>
      <header className={styles.pageHeader}>
        <div>
          <h1>Offering</h1>
          <p>Products that can be licensed to tenants.</p>
        </div>
        <Button type="button" onClick={openCreate}><Plus size={16} aria-hidden="true" /> Create offering</Button>
      </header>

      {notice && <Alert tone="success" title="Catalog updated">{notice}</Alert>}
      {error && !editorOpen && <Alert tone="error" title="Action unavailable">{error}</Alert>}

      <section className={styles.tableCard} aria-label="Offering catalog">
        <div className={styles.toolbar}>
          <label className={styles.searchField}><Search size={16} aria-hidden="true" /><span className={styles.srOnly}>Search offerings</span><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search offerings" /></label>
          <label className={styles.filterField}><span className={styles.srOnly}>Role type</span><select value={roleTypeFilter} onChange={(event) => setRoleTypeFilter(event.target.value as typeof roleTypeFilter)} aria-label="Role type"><option value="">All role types</option><option value="PLATFORM">Platform</option><option value="TENANT">Tenant</option><option value="BOTH">Platform / Tenant</option></select></label>
          <label className={styles.filterField}><span className={styles.srOnly}>Status</span><select value={statusFilter} onChange={(event) => setStatusFilter(event.target.value as typeof statusFilter)} aria-label="Status"><option value="">All statuses</option><option value="ACTIVE">Active</option><option value="INACTIVE">Inactive</option></select></label>
          <div className={styles.catalogMeta}><span>{offerings === null ? "Loading…" : `${offerings.length} ${offerings.length === 1 ? "offering" : "offerings"}`}</span><Button type="button" variant="ghost" onClick={() => setRefreshVersion((current) => current + 1)} aria-label="Refresh offerings"><RefreshCw size={16} aria-hidden="true" /></Button></div>
        </div>
        <div className={styles.tableScroll}>
          <table>
            <thead><tr><th>Offering</th><th>Role type</th><th>Status</th><th>Usage</th><th>Edit</th><th>Enable / Disable</th><th>Delete</th></tr></thead>
            <tbody>
              {(offerings ?? []).map((offering) => {
                const isInUse = offering.tenant_entitlement_count > 0 || offering.configuration_category_count > 0;
                const roleType = offering.role_type ?? "TENANT";
                return <tr key={offering.offering_id}>
                  <td><strong>{offering.display_name}</strong><span>{offering.code} · {offering.description}</span></td>
                  <td><span className={`${styles.roleBadge} ${styles[`role${roleType}`]}`}>{roleTypeLabels[roleType]}</span></td>
                  <td><span className={`${styles.badge} ${offering.status === "ACTIVE" ? styles.active : styles.inactive}`}>{offering.status === "ACTIVE" ? "Active" : "Inactive"}</span></td>
                  <td><strong>{offering.tenant_entitlement_count} entitlements</strong><span>{offering.configuration_category_count} config categories</span></td>
                  <td className={styles.actionCell}><Button type="button" variant="ghost" onClick={() => openEdit(offering)}><Pencil size={15} aria-hidden="true" /> Edit</Button></td>
                  <td className={styles.actionCell}><Button type="button" variant="ghost" onClick={() => setPendingAction(offering)}><Power size={15} aria-hidden="true" /> {offering.status === "ACTIVE" ? "Disable" : "Enable"}</Button></td>
                  <td className={styles.actionCell}><Button type="button" variant="ghost" disabled={isInUse} title={isInUse ? "Offerings with tenant entitlements or configuration categories cannot be deleted." : "Delete offering"} onClick={() => setPendingDelete(offering)}><Trash2 size={15} aria-hidden="true" /> Delete</Button></td>
                </tr>;
              })}
              {offerings === null && <tr><td className={styles.empty} colSpan={7}>Loading offerings…</td></tr>}
              {offerings !== null && offerings.length === 0 && <tr><td className={styles.empty} colSpan={7}><Package size={22} aria-hidden="true" /> No offerings match these filters.</td></tr>}
            </tbody>
          </table>
        </div>
      </section>

      {editorOpen && (
        <div className={styles.backdrop} onMouseDown={(event) => { if (event.target === event.currentTarget && !submitting) closeEditor(); }}>
          <form className={styles.dialog} role="dialog" aria-modal="true" aria-labelledby="offering-editor-title" onSubmit={(event) => { void submitEditor(event); }}>
            <div className={styles.dialogHeader}>
              <div><h2 ref={editorTitleRef} id="offering-editor-title" tabIndex={-1}>{editingId ? "Edit offering" : "Create offering"}</h2><p>{editingId ? "Update the offering details and operating level. The offering code cannot be changed." : "Add a product to the catalog and choose where it operates."}</p></div>
              <button type="button" className={styles.closeButton} onClick={closeEditor} disabled={submitting} aria-label="Close offering form"><X size={18} aria-hidden="true" /></button>
            </div>
            {error && <Alert tone="error" title="Offering could not be saved">{error}</Alert>}
            <div className={styles.editorForm}>
              <label><span>Display name</span><input value={editor.display_name} onChange={(event) => updateEditor("display_name", event.target.value)} required maxLength={100} /></label>
              <label><span>Offering code</span><input value={editor.code} onChange={(event) => updateEditor("code", event.target.value.toUpperCase())} required disabled={Boolean(editingId)} pattern="[A-Z][A-Z0-9_]{1,49}" title="Uppercase letters, numbers, and underscores" /></label>
              <label><span>Role type</span><select required value={editor.role_type} onChange={(event) => updateEditor("role_type", event.target.value as EditorValues["role_type"])}><option value="" disabled>Select role type</option><option value="PLATFORM">Platform</option><option value="TENANT">Tenant</option><option value="BOTH">Platform / Tenant</option></select></label>
              <label><span>Display order</span><input type="number" min={0} value={editor.sort_order} onChange={(event) => updateEditor("sort_order", Number(event.target.value))} required /></label>
              {!editingId && <label><span>Initial status</span><select value={editor.status} onChange={(event) => updateEditor("status", event.target.value as EditorValues["status"])}><option value="INACTIVE">Inactive</option><option value="ACTIVE">Active</option></select></label>}
              <div className={styles.iconPicker}>
                <span>Offering icon</span>
                <button className={styles.iconTrigger} type="button" aria-expanded={iconPickerOpen} onClick={() => setIconPickerOpen((open) => !open)}><SelectedIcon size={18} aria-hidden="true" /> Choose an icon</button>
                {iconPickerOpen && <div className={styles.iconPanel} role="dialog" aria-label="Choose an offering icon">
                  <label className={styles.iconSearch}><Search size={15} aria-hidden="true" /><input value={iconQuery} onChange={(event) => setIconQuery(event.target.value)} placeholder="Search icons" autoFocus /></label>
                  <div className={styles.iconTabs} role="tablist" aria-label="Icon categories">{iconCategories.map((category) => <button type="button" role="tab" aria-selected={iconCategory === category} className={iconCategory === category ? styles.activeIconTab : ""} key={category} onClick={() => setIconCategory(category)}>{category}</button>)}</div>
                  <div className={styles.iconGrid}>{visibleIcons.map(({ key, label, Icon }) => <button className={editor.icon_key === key ? styles.selectedIcon : ""} type="button" key={key} title={label} aria-label={label} aria-pressed={editor.icon_key === key} onClick={() => { updateEditor("icon_key", key); setIconPickerOpen(false); }}><Icon size={20} aria-hidden="true" /><span>{label}</span></button>)}</div>
                  {visibleIcons.length === 0 && <p className={styles.noIcons}>No icons match this search.</p>}
                </div>}
              </div>
              <label className={styles.description}><span>Description</span><textarea value={editor.description} onChange={(event) => updateEditor("description", event.target.value)} required maxLength={5000} rows={4} /></label>
            </div>
            <div className={styles.dialogActions}><Button type="button" variant="secondary" onClick={closeEditor} disabled={submitting}>Cancel</Button><Button type="submit" loading={submitting}>{editingId ? "Save changes" : "Create offering"}</Button></div>
          </form>
        </div>
      )}

      <ConfirmDialog open={pendingAction !== null} title={pendingAction?.status === "ACTIVE" ? "Disable offering?" : "Enable offering?"} description={pendingAction?.status === "ACTIVE" ? "This blocks new assignments. Existing tenant access is preserved." : pendingAction?.role_type === "PLATFORM" ? "This makes the offering active in the platform catalog." : "This makes the offering available for tenant registration and future grants."} confirmLabel={pendingAction?.status === "ACTIVE" ? "Disable offering" : "Enable offering"} destructive={pendingAction?.status === "ACTIVE"} busy={actionBusy} onCancel={() => setPendingAction(null)} onConfirm={() => { void confirmStatus(); }} />
      <ConfirmDialog open={pendingDelete !== null} title="Delete offering?" description="This permanently removes an unused offering from the catalog. This cannot be undone." confirmLabel="Delete offering" destructive reason={deleteReason} reasonLabel="Reason for deletion" reasonRequired busy={actionBusy} onReasonChange={setDeleteReason} onCancel={() => { setPendingDelete(null); setDeleteReason(""); }} onConfirm={() => { void confirmDelete(); }} />
    </div>
  );
};
