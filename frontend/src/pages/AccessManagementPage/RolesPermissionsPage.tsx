import { Lock, Pencil, Plus, Search, Shield, X } from "lucide-react";
import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";

import {
  createPlatformRole,
  createTenantRole,
  listPlatformPageAccess,
  listPlatformPages,
  listPlatformRoles,
  listPlatformUsers,
  listTenantPageAccess,
  listTenantPages,
  listTenantRoles,
  listTenantUsers,
  savePlatformPageAccess,
  saveTenantPageAccess,
  updatePlatformRole,
  updateTenantRole,
  type AccessLevel,
  type Page,
  type PageAccess,
  type PlatformUser,
  type Role,
  type TenantUser,
} from "../../features/access-management/api/access-management-api";
import { defaultRolesApi } from "../../features/default-role-management/api/default-roles-api";
import type { DefaultRoleListItem } from "../../features/default-role-management/model/default-roles";
import { offeringsApi } from "../../features/offering-management/api/offerings-api";
import type { OfferingCatalogItem } from "../../features/offering-management/model/offerings";
import { useSession } from "../../entities/session/model/session-context";
import { getLoginErrorContent } from "../../features/auth/model/login-errors";
import { Alert } from "../../shared/ui/Alert/Alert";
import { Button } from "../../shared/ui/Button/Button";
import { InputField } from "../../shared/ui/InputField/InputField";
import { ApiError } from "../../shared/api/errors";
import styles from "./AccessManagementPage.module.css";
import type { AccessRealm } from "./UsersManagementPage";

const accessLevels: AccessLevel[] = ["none", "view", "modify"];
const accessLevelLabels: Record<AccessLevel, string> = {
  none: "None",
  view: "View",
  modify: "Modify",
};

const toRoleCode = (name: string) =>
  name
    .trim()
    .toUpperCase()
    .replace(/[^A-Z0-9]+/g, "_")
    .replace(/^_+|_+$/g, "") || "CUSTOM_ROLE";

const errorMessage = (caught: unknown) =>
  caught instanceof ApiError ? caught.message : getLoginErrorContent(caught).message;

const humanModule = (value: string) =>
  value
    .replaceAll("_", " ")
    .replace(/\b\w/g, (letter) => letter.toUpperCase());

const isSensitivePage = (page: Page) =>
  /USER|ROLE|CONFIG|ACCESS|ADMIN|PERMISSION/i.test(`${page.page_code} ${page.page_name}`);

interface RolesPermissionsPageProps {
  realm: AccessRealm;
}

const toListedRole = (item: DefaultRoleListItem): Role => ({
  role_id: item.role_id,
  role_code: item.role_code,
  role_name: item.role_name,
  description: item.description,
  is_system: item.is_system,
  is_active: item.is_active,
  module_scope: item.module_scope,
  users_count: 0,
  created_at: item.created_at,
});

const emptyRoleForm = {
  role_name: "",
  role_code: "",
  description: "",
  module_scope: "",
  role_type: "platform" as "platform" | "tenant",
};

export const RolesPermissionsPage = ({ realm }: RolesPermissionsPageProps) => {
  const { principal } = useSession();
  const [searchParams, setSearchParams] = useSearchParams();
  const roleKind = realm === "tenant" ? "tenant" : searchParams.get("type") === "tenant" ? "tenant" : "platform";
  const offeringId = roleKind === "tenant" ? (searchParams.get("offering_id") ?? "") : "";
  const coreSelected = roleKind === "tenant" && !offeringId;
  const [roles, setRoles] = useState<Role[]>([]);
  const [selectedRoleId, setSelectedRoleId] = useState("");
  const [pageAccess, setPageAccess] = useState<PageAccess[]>([]);
  const [originalAccess, setOriginalAccess] = useState<PageAccess[]>([]);
  const [templateVersion, setTemplateVersion] = useState(1);
  const [offerings, setOfferings] = useState<OfferingCatalogItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const [sensitiveOnly, setSensitiveOnly] = useState(false);
  const [detailTab, setDetailTab] = useState<"permissions" | "users">("permissions");
  const [assignedUsers, setAssignedUsers] = useState<Array<{ id: string; name: string; email: string }>>([]);
  const [createOpen, setCreateOpen] = useState(false);
  const [editOpen, setEditOpen] = useState(false);
  const [roleForm, setRoleForm] = useState(emptyRoleForm);
  const [catalogPages, setCatalogPages] = useState<Page[]>([]);

  const isTenantTemplate = realm === "platform" && roleKind === "tenant";
  const licensedOfferings = principal?.principal_type === "tenant_user" ? principal.tenant.offerings : [];
  const showOfferingFilter = realm === "tenant" || isTenantTemplate;
  const selectedOffering =
    realm === "tenant"
      ? licensedOfferings.find((item) => item.offering_id === offeringId)
      : offerings.find((item) => item.offering_id === offeringId);
  const activeModuleCode =
    realm === "tenant" ? (selectedOffering?.code ?? "CORE") : selectedOffering?.code ?? (coreSelected ? "CORE" : "");
  const moduleRoles = useMemo(() => {
    if (realm !== "tenant") return roles;
    return roles.filter((role) => {
      const scope = role.module_scope || "CORE";
      return activeModuleCode === "CORE" ? scope === "CORE" : scope === activeModuleCode;
    });
  }, [activeModuleCode, realm, roles]);
  const selectedRole = moduleRoles.find((role) => role.role_id === selectedRoleId) ?? null;
  const unsavedCount = useMemo(
    () =>
      pageAccess.filter(
        (entry) =>
          originalAccess.find((item) => item.page.page_id === entry.page.page_id)?.access_level !==
          entry.access_level,
      ).length,
    [originalAccess, pageAccess],
  );

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      if (realm === "platform") {
        const catalog = await offeringsApi.list();
        setOfferings(catalog);
      }
      if (realm === "platform" && roleKind === "tenant") {
        const templates = await defaultRolesApi.list({
          offeringId: offeringId || null,
          coreOnly: !offeringId,
        });
        setRoles(templates.map(toListedRole));
        setCatalogPages([]);
        setSelectedRoleId((current) =>
          templates.some((item) => item.role_id === current) ? current : templates[0]?.role_id || "",
        );
        return;
      }
      const [rolesResult, pagesResult] = await Promise.all([
        realm === "platform" ? listPlatformRoles() : listTenantRoles(),
        realm === "platform" ? listPlatformPages() : listTenantPages(),
      ]);
      setRoles(rolesResult);
      setCatalogPages(pagesResult);
      setSelectedRoleId((current) =>
        rolesResult.some((role) => role.role_id === current) ? current : rolesResult[0]?.role_id || "",
      );
    } catch (caught) {
      setError(errorMessage(caught));
    } finally {
      setLoading(false);
    }
  }, [offeringId, realm, roleKind]);

  useEffect(() => {
    void load();
  }, [load]);

  useEffect(() => {
    if (!selectedRoleId) {
      setPageAccess([]);
      setOriginalAccess([]);
      return;
    }
    const scopedRoles = realm === "tenant" ? moduleRoles : roles;
    if (scopedRoles.length > 0 && !scopedRoles.some((role) => role.role_id === selectedRoleId)) {
      return;
    }
    const loadAccess = async () => {
      try {
        if (realm === "platform" && roleKind === "tenant") {
          const detail = await defaultRolesApi.get(selectedRoleId);
          setPageAccess(detail.page_access);
          setOriginalAccess(detail.page_access);
          setTemplateVersion(detail.version);
          return;
        }
        const access =
          realm === "platform"
            ? await listPlatformPageAccess(selectedRoleId)
            : await listTenantPageAccess(selectedRoleId);
        setPageAccess(access);
        setOriginalAccess(access);
      } catch (caught) {
        setError(errorMessage(caught));
      }
    };
    void loadAccess();
  }, [moduleRoles, realm, roleKind, roles, selectedRoleId]);

  useEffect(() => {
    if (detailTab !== "users" || !selectedRole) {
      setAssignedUsers([]);
      return;
    }
    const loadUsers = async () => {
      try {
        if (isTenantTemplate) {
          setAssignedUsers([]);
          return;
        }
        if (realm === "platform") {
          const users = await listPlatformUsers();
          setAssignedUsers(
            users
              .filter((user) => user.roles.some((role) => role.role_id === selectedRole.role_id))
              .map((user: PlatformUser) => ({ id: user.admin_id, name: user.name, email: user.email })),
          );
          return;
        }
        const users = await listTenantUsers();
        setAssignedUsers(
          users
            .filter((user: TenantUser) => user.roles.includes(selectedRole.role_name) || user.role === selectedRole.role_name)
            .map((user) => ({ id: user.user_id, name: user.name, email: user.email })),
        );
      } catch {
        setAssignedUsers([]);
      }
    };
    void loadUsers();
  }, [detailTab, isTenantTemplate, realm, selectedRole]);

  useEffect(() => {
    if (moduleRoles.some((role) => role.role_id === selectedRoleId)) return;
    setSelectedRoleId(moduleRoles[0]?.role_id || "");
  }, [moduleRoles, selectedRoleId]);

  const tenantModuleOptions = useMemo(() => {
    const source = realm === "tenant" ? licensedOfferings : offerings;
    return [
      { value: "CORE", label: "Workspace" },
      ...source.map((offering) => ({ value: offering.code, label: offering.display_name })),
    ];
  }, [licensedOfferings, offerings, realm]);

  const grouped = useMemo(() => {
    const filtered = pageAccess.filter((entry) => {
      if (sensitiveOnly && !isSensitivePage(entry.page)) return false;
      const haystack = `${entry.page.module} ${entry.page.page_name} ${entry.page.page_code} ${entry.page.route}`.toLowerCase();
      return haystack.includes(query.trim().toLowerCase());
    });
    const modules = new Map<string, PageAccess[]>();
    for (const entry of filtered) {
      const key = entry.page.module || entry.page.offering_code || "General";
      modules.set(key, [...(modules.get(key) ?? []), entry]);
    }
    return [...modules.entries()];
  }, [pageAccess, query, sensitiveOnly]);

  const setModuleAccess = (moduleKey: string, accessLevel: AccessLevel) => {
    setPageAccess((current) =>
      current.map((entry) => {
        const key = entry.page.module || entry.page.offering_code || "workspace";
        return key === moduleKey ? { ...entry, access_level: accessLevel } : entry;
      }),
    );
  };

  const selectRoleKind = (nextKind: "platform" | "tenant") => {
    if (realm === "tenant") return;
    const next = new URLSearchParams(searchParams);
    if (nextKind === "tenant") {
      next.set("type", "tenant");
    } else {
      next.delete("type");
      next.delete("offering_id");
      next.delete("scope");
    }
    setSelectedRoleId("");
    setDetailTab("permissions");
    setSearchParams(next, { replace: true });
  };

  const selectOfferingModule = (id: string) => {
    const next = new URLSearchParams(searchParams);
    if (realm === "platform") next.set("type", "tenant");
    if (id === "core") next.delete("offering_id");
    else next.set("offering_id", id);
    setSelectedRoleId("");
    setDetailTab("permissions");
    setQuery("");
    setSearchParams(next, { replace: true });
  };

  const openCreate = () => {
    setCreateOpen(true);
    setError(null);
    setRoleForm({
      ...emptyRoleForm,
      role_type: realm === "tenant" ? "tenant" : roleKind,
      module_scope: roleKind === "tenant" ? (selectedOffering?.code ?? "CORE") : catalogPages[0]?.module ?? "",
    });
  };

  const handleCreateRole = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setSaving(true);
    setError(null);
    try {
      const createAsTenant = realm === "tenant" || roleForm.role_type === "tenant";
      const payload = {
        role_name: roleForm.role_name,
        role_code: toRoleCode(roleForm.role_code || roleForm.role_name),
        description: roleForm.description || undefined,
        module_scope: roleForm.module_scope || undefined,
      };
      let role: Role;
      if (realm === "platform" && createAsTenant) {
        const selectedCreateOffering = offerings.find((item) => item.code === roleForm.module_scope);
        const created = await defaultRolesApi.create({
          role_name: payload.role_name,
          role_code: payload.role_code,
          description: payload.description ?? null,
          offering_id: selectedCreateOffering?.offering_id ?? null,
        });
        role = toListedRole(created);
        const next = new URLSearchParams(searchParams);
        next.set("type", "tenant");
        if (selectedCreateOffering) next.set("offering_id", selectedCreateOffering.offering_id);
        else next.delete("offering_id");
        setSearchParams(next, { replace: true });
      } else {
        role = realm === "platform" ? await createPlatformRole(payload) : await createTenantRole(payload);
        if (realm === "tenant") {
          const createdOffering = licensedOfferings.find((item) => item.code === payload.module_scope);
          const next = new URLSearchParams(searchParams);
          if (createdOffering) next.set("offering_id", createdOffering.offering_id);
          else next.delete("offering_id");
          setSearchParams(next, { replace: true });
        } else if (realm === "platform" && roleKind !== "platform") {
          const next = new URLSearchParams(searchParams);
          next.delete("type");
          next.delete("offering_id");
          next.delete("scope");
          setSearchParams(next, { replace: true });
        }
      }
      setRoleForm(emptyRoleForm);
      setCreateOpen(false);
      setNotice(`${role.role_name} created. Set None, View, or Modify, then save.`);
      setSelectedRoleId(role.role_id);
      await load();
      setSelectedRoleId(role.role_id);
    } catch (caught) {
      setError(errorMessage(caught));
    } finally {
      setSaving(false);
    }
  };

  const handleEditRole = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!selectedRoleId) return;
    setSaving(true);
    setError(null);
    try {
      const payload = {
        role_name: roleForm.role_name,
        description: roleForm.description || null,
      };
      if (isTenantTemplate) {
        await defaultRolesApi.update(selectedRoleId, {
          role_name: payload.role_name,
          description: payload.description,
          version: templateVersion,
        });
      } else {
        const role =
          realm === "platform"
            ? await updatePlatformRole(selectedRoleId, payload)
            : await updateTenantRole(selectedRoleId, payload);
        setNotice(`${role.role_name} updated.`);
        setEditOpen(false);
        await load();
        setSelectedRoleId(role.role_id);
        return;
      }
      setEditOpen(false);
      setNotice(`${roleForm.role_name} updated.`);
      await load();
      setSelectedRoleId(selectedRoleId);
    } catch (caught) {
      setError(errorMessage(caught));
    } finally {
      setSaving(false);
    }
  };

  const handleSave = async () => {
    if (!selectedRoleId) return;
    setSaving(true);
    setError(null);
    try {
      const entries = pageAccess.map((entry) => ({
        page_id: entry.page.page_id,
        access_level: entry.access_level,
      }));
      if (isTenantTemplate) {
        const saved = await defaultRolesApi.update(selectedRoleId, {
          version: templateVersion,
          entries,
        });
        setPageAccess(saved.page_access);
        setOriginalAccess(saved.page_access);
        setTemplateVersion(saved.version);
        setNotice("Page access saved.");
        return;
      }
      const saved =
        realm === "platform"
          ? await savePlatformPageAccess(selectedRoleId, entries)
          : await saveTenantPageAccess(selectedRoleId, entries);
      setPageAccess(saved);
      setOriginalAccess(saved);
      setNotice("Page access saved.");
    } catch (caught) {
      setError(errorMessage(caught));
    } finally {
      setSaving(false);
    }
  };

  return (
    <section className={`${styles.page} ${styles.rolesPage}`}>
      <header className={styles.rolesHeader}>
        <div>
          <p>Access control</p>
          <h1>Roles & permissions</h1>
          <span className={styles.lede}>
            {realm === "tenant"
              ? "Create tenant roles and grant page access for Workspace and licensed modules."
              : roleKind === "tenant"
                ? "Define default tenant roles that are copied when a workspace is registered."
                : "Manage platform console roles and the pages each role can view or modify."}
          </span>
        </div>
        <div className={styles.studioPageActions}>
          <Button type="button" onClick={openCreate}>
            <Plus size={16} aria-hidden="true" />
            New role
          </Button>
        </div>
      </header>

      {error && !createOpen && !editOpen && <Alert tone="error">{error}</Alert>}
      {notice && <Alert tone="success">{notice}</Alert>}

      {loading ? (
        <div className={styles.loading}>Loading roles…</div>
      ) : !selectedRole ? (
        <div className={styles.rolesEmpty}>
          <Shield size={28} aria-hidden="true" />
          <h2>Create a role to set page access</h2>
          <p>
            {realm === "tenant"
              ? "Choose Workspace or a licensed module such as Task Management, then assign None, View, or Modify."
              : "Pick Platform or Tenant, create a role, then set page access."}
          </p>
          {showOfferingFilter && (
            <label className={styles.offeringFilter}>
              Offering
              <select
                aria-label="Offering"
                value={coreSelected ? "core" : offeringId}
                onChange={(event) => selectOfferingModule(event.target.value)}
              >
                <option value="core">Workspace</option>
                {(realm === "tenant" ? licensedOfferings : offerings).map((offering) => (
                  <option key={offering.offering_id} value={offering.offering_id}>
                    {offering.display_name}
                  </option>
                ))}
              </select>
            </label>
          )}
          <Button type="button" onClick={openCreate}>
            <Plus size={16} aria-hidden="true" />
            New role
          </Button>
        </div>
      ) : (
        <article className={styles.studio}>
          <div className={styles.studioHeader}>
            <div>
              <h2>{selectedRole.role_name}</h2>
              <p>Code: {selectedRole.role_code}</p>
            </div>
            <div className={styles.studioActions}>
              <Button
                type="button"
                variant="secondary"
                onClick={() => {
                  setRoleForm({
                    role_name: selectedRole.role_name,
                    role_code: selectedRole.role_code,
                    description: selectedRole.description ?? "",
                    module_scope: selectedRole.module_scope ?? "",
                    role_type: roleKind,
                  });
                  setEditOpen(true);
                  setError(null);
                }}
              >
                <Pencil size={15} aria-hidden="true" />
                Edit details
              </Button>
              <Button type="button" onClick={() => void handleSave()} loading={saving} disabled={unsavedCount === 0}>
                Save changes
              </Button>
            </div>
          </div>

          {realm === "platform" && (
            <div className={styles.typeRow}>
              <span>Role type</span>
              <label>
                <input
                  type="radio"
                  name="catalog-role-type"
                  checked={roleKind === "platform"}
                  onChange={() => selectRoleKind("platform")}
                />
                Platform
              </label>
              <label>
                <input
                  type="radio"
                  name="catalog-role-type"
                  checked={roleKind === "tenant"}
                  onChange={() => selectRoleKind("tenant")}
                />
                Tenant
              </label>
              <small>
                <Lock size={12} aria-hidden="true" />
                Locked once users are assigned
              </small>
            </div>
          )}

          <div className={styles.summaryRow}>
            <article>
              <small>Status</small>
              <strong>{selectedRole.is_active ? "Active" : "Inactive"}</strong>
            </article>
            <article>
              <small>System role</small>
              <strong>{selectedRole.is_system ? "System" : "Custom"}</strong>
            </article>
            <article>
              <small>Users assigned</small>
              <strong>{isTenantTemplate ? "—" : selectedRole.users_count}</strong>
            </article>
            <label className={styles.offeringCard}>
              <small>{showOfferingFilter ? "Roles in offering" : "Roles"}</small>
              <select
                aria-label={showOfferingFilter ? "Roles in offering" : "Roles"}
                value={selectedRoleId}
                onChange={(event) => {
                  setSelectedRoleId(event.target.value);
                  setQuery("");
                  setDetailTab("permissions");
                }}
              >
                {moduleRoles.map((role) => (
                  <option key={role.role_id} value={role.role_id}>
                    {role.role_name}
                  </option>
                ))}
              </select>
            </label>
            {showOfferingFilter && (
              <label className={styles.offeringCard}>
                <small>Offering</small>
                <select
                  aria-label="Offering"
                  value={coreSelected ? "core" : offeringId}
                  onChange={(event) => selectOfferingModule(event.target.value)}
                >
                  <option value="core">Workspace</option>
                  {(realm === "tenant" ? licensedOfferings : offerings).map((offering) => (
                    <option key={offering.offering_id} value={offering.offering_id}>
                      {offering.display_name}
                    </option>
                  ))}
                </select>
              </label>
            )}
          </div>

          <div className={styles.studioTabs}>
            <button
              type="button"
              className={detailTab === "permissions" ? styles.studioTabActive : ""}
              onClick={() => setDetailTab("permissions")}
            >
              Permissions
            </button>
            <button
              type="button"
              className={detailTab === "users" ? styles.studioTabActive : ""}
              onClick={() => setDetailTab("users")}
            >
              Users assigned
            </button>
          </div>

          {detailTab === "permissions" ? (
            <>
              <div className={styles.studioToolbar}>
                <InputField
                  id={`${realm}-permission-search`}
                  label="Search permissions"
                  placeholder="Search permissions by module, page, or code"
                  value={query}
                  onChange={(event) => setQuery(event.target.value)}
                  leadingIcon={<Search size={16} />}
                />
                <button
                  type="button"
                  className={`${styles.sensitiveToggle} ${sensitiveOnly ? styles.sensitiveOn : ""}`}
                  aria-pressed={sensitiveOnly}
                  onClick={() => setSensitiveOnly((current) => !current)}
                >
                  Sensitive only
                </button>
              </div>
              {grouped.map(([module, entries]) => (
                <section className={styles.permGroup} key={module}>
                  <header>
                    <div>
                      <h3>{humanModule(module)}</h3>
                      <span>{entries.length} {entries.length === 1 ? "page" : "pages"}</span>
                    </div>
                    <div className={styles.bulk}>
                      <button type="button" onClick={() => setModuleAccess(module, "none")}>None</button>
                      <button type="button" className={styles.bulkView} onClick={() => setModuleAccess(module, "view")}>View all</button>
                      <button type="button" className={styles.bulkModify} onClick={() => setModuleAccess(module, "modify")}>Modify all</button>
                    </div>
                  </header>
                  {entries.map((entry) => (
                    <div className={styles.permRow} key={entry.page.page_id}>
                      <div>
                        <strong>{entry.page.page_name}</strong>
                        <small>{entry.page.page_code}</small>
                      </div>
                      <div className={styles.segmented} role="group" aria-label={`${entry.page.page_name} access`}>
                        {accessLevels.map((level) => (
                          <button
                            type="button"
                            key={level}
                            className={
                              entry.access_level === level
                                ? `${styles.segmentActive} ${level === "none" ? styles.segmentNone : ""} ${level === "view" ? styles.segmentView : ""}`
                                : ""
                            }
                            onClick={() =>
                              setPageAccess((current) =>
                                current.map((item) =>
                                  item.page.page_id === entry.page.page_id ? { ...item, access_level: level } : item,
                                ),
                              )
                            }
                          >
                            {accessLevelLabels[level]}
                          </button>
                        ))}
                      </div>
                    </div>
                  ))}
                </section>
              ))}
              {grouped.length === 0 && (
                <div className={styles.empty}>
                  {sensitiveOnly || query
                    ? "No pages match this search."
                    : "No pages are available for this role yet."}
                </div>
              )}
            </>
          ) : (
            <div className={styles.assignedList}>
              {isTenantTemplate && (
                <p>Tenant default roles are copied at registration. Assign users inside each tenant.</p>
              )}
              {assignedUsers.length === 0 && !isTenantTemplate && (
                <p>No users are assigned to this role yet.</p>
              )}
              {assignedUsers.map((user) => (
                <article key={user.id}>
                  <strong>{user.name}</strong>
                  <span>{user.email}</span>
                </article>
              ))}
            </div>
          )}
        </article>
      )}

      {createOpen && (
        <div className={styles.backdrop}>
          <form className={styles.dialog} role="dialog" aria-labelledby={`${realm}-new-role-title`} onSubmit={handleCreateRole}>
            <div className={styles.dialogHeader}>
              <div>
                <h2 id={`${realm}-new-role-title`}>New role</h2>
                <p>
                  {realm === "tenant"
                    ? "Choose a licensed module. Permissions will include only that module’s pages."
                    : "Platform roles use the console. Tenant defaults use Workspace or a licensed module."}
                </p>
              </div>
              <button type="button" className={styles.close} onClick={() => setCreateOpen(false)} aria-label="Close">
                <X size={18} />
              </button>
            </div>
            {error && <Alert tone="error">{error}</Alert>}
            <div className={styles.formGrid}>
              <div className={styles.span2}>
                <InputField
                  id={`${realm}-new-role-name`}
                  label="Role name"
                  value={roleForm.role_name}
                  onChange={(event) => setRoleForm((current) => ({ ...current, role_name: event.target.value }))}
                  required
                />
              </div>
              {realm === "platform" && (
                <fieldset className={styles.span2}>
                  <legend>Role type</legend>
                  <div className={styles.typeChoices}>
                    <label>
                      <input
                        type="radio"
                        name="new-role-type"
                        checked={roleForm.role_type === "platform"}
                        onChange={() => setRoleForm((current) => ({ ...current, role_type: "platform", module_scope: catalogPages[0]?.module ?? "" }))}
                      />
                      Platform
                    </label>
                    <label>
                      <input
                        type="radio"
                        name="new-role-type"
                        checked={roleForm.role_type === "tenant"}
                        onChange={() => setRoleForm((current) => ({ ...current, role_type: "tenant", module_scope: "CORE" }))}
                      />
                      Tenant
                    </label>
                  </div>
                </fieldset>
              )}
              {roleForm.role_type === "tenant" && (
                <label className={styles.span2}>
                  Module
                  <select
                    required
                    aria-label="Module"
                    value={roleForm.module_scope}
                    onChange={(event) => setRoleForm((current) => ({ ...current, module_scope: event.target.value }))}
                  >
                    {tenantModuleOptions.map((option) => (
                      <option key={option.value} value={option.value}>{option.label}</option>
                    ))}
                  </select>
                </label>
              )}
              <div className={styles.span2}>
                <InputField
                  id={`${realm}-new-role-code`}
                  label="Role code"
                  value={roleForm.role_code}
                  onChange={(event) =>
                    setRoleForm((current) => ({
                      ...current,
                      role_code: event.target.value.toUpperCase().replace(/[^A-Z0-9_]/g, "_"),
                    }))
                  }
                  hint="Optional. Generated from the name if blank."
                />
              </div>
              <div className={styles.span2}>
                <InputField
                  id={`${realm}-new-role-description`}
                  label="Description"
                  value={roleForm.description}
                  onChange={(event) => setRoleForm((current) => ({ ...current, description: event.target.value }))}
                />
              </div>
            </div>
            <div className={styles.dialogActions}>
              <Button type="button" variant="secondary" onClick={() => setCreateOpen(false)}>Cancel</Button>
              <Button type="submit" loading={saving} loadingLabel="Creating…">Create role</Button>
            </div>
          </form>
        </div>
      )}

      {editOpen && selectedRole && (
        <div className={styles.backdrop}>
          <form className={styles.dialog} role="dialog" aria-labelledby={`${realm}-edit-role-title`} onSubmit={handleEditRole}>
            <div className={styles.dialogHeader}>
              <div>
                <h2 id={`${realm}-edit-role-title`}>Edit details</h2>
                <p>Update the name and description. The module cannot be changed after the role is created.</p>
              </div>
              <button type="button" className={styles.close} onClick={() => setEditOpen(false)} aria-label="Close">
                <X size={18} />
              </button>
            </div>
            {error && <Alert tone="error">{error}</Alert>}
            <div className={styles.formGrid}>
              <div className={styles.span2}>
                <InputField
                  id={`${realm}-edit-role-name`}
                  label="Role name"
                  value={roleForm.role_name}
                  onChange={(event) => setRoleForm((current) => ({ ...current, role_name: event.target.value }))}
                  required
                />
              </div>
              <div className={styles.span2}>
                <InputField
                  id={`${realm}-edit-role-code`}
                  label="Role code"
                  value={roleForm.role_code}
                  disabled
                  hint="Role codes cannot be changed after creation."
                />
              </div>
              <div className={styles.span2}>
                <InputField
                  id={`${realm}-edit-role-description`}
                  label="Description"
                  value={roleForm.description}
                  onChange={(event) => setRoleForm((current) => ({ ...current, description: event.target.value }))}
                />
              </div>
            </div>
            <div className={styles.dialogActions}>
              <Button type="button" variant="secondary" onClick={() => setEditOpen(false)}>Cancel</Button>
              <Button type="submit" loading={saving} loadingLabel="Saving…">Save role</Button>
            </div>
          </form>
        </div>
      )}
    </section>
  );
};
