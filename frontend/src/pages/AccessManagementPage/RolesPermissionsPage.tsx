import { Pencil, Plus, Search, Trash2, X } from "lucide-react";
import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";

import {
  createPlatformRole,
  createTenantRole,
  deletePlatformRole,
  deleteTenantRole,
  listPlatformPageAccess,
  listPlatformPages,
  listPlatformRoles,
  listTenantPageAccess,
  listTenantPages,
  listTenantRoles,
  savePlatformPageAccess,
  saveTenantPageAccess,
  updatePlatformRole,
  updateTenantRole,
  type AccessLevel,
  type Page,
  type PageAccess,
  type Role,
} from "../../features/access-management/api/access-management-api";
import { useSession } from "../../entities/session/model/session-context";
import { getLoginErrorContent } from "../../features/auth/model/login-errors";
import { Alert } from "../../shared/ui/Alert/Alert";
import { Button } from "../../shared/ui/Button/Button";
import { InputField } from "../../shared/ui/InputField/InputField";
import { ApiError } from "../../shared/api/errors";
import styles from "./AccessManagementPage.module.css";
import type { AccessRealm } from "./UsersManagementPage";

const accessLevels: AccessLevel[] = ["none", "view", "modify"];

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

interface RolesPermissionsPageProps {
  realm: AccessRealm;
}

export const RolesPermissionsPage = ({ realm }: RolesPermissionsPageProps) => {
  const { principal } = useSession();
  const [roles, setRoles] = useState<Role[]>([]);
  const [selectedRoleId, setSelectedRoleId] = useState("");
  const [pageAccess, setPageAccess] = useState<PageAccess[]>([]);
  const [originalAccess, setOriginalAccess] = useState<PageAccess[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const [moduleFilter, setModuleFilter] = useState("all");
  const [createOpen, setCreateOpen] = useState(false);
  const [editOpen, setEditOpen] = useState(false);
  const [roleForm, setRoleForm] = useState({ role_name: "", role_code: "", description: "", module_scope: "" });
  const [catalogPages, setCatalogPages] = useState<Page[]>([]);

  const selectedRole = roles.find((role) => role.role_id === selectedRoleId) ?? null;
  const unsaved = useMemo(
    () =>
      pageAccess.some(
        (entry) =>
          originalAccess.find((item) => item.page.page_id === entry.page.page_id)?.access_level !==
          entry.access_level,
      ),
    [originalAccess, pageAccess],
  );

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [rolesResult, pagesResult] = await Promise.all([
        realm === "platform" ? listPlatformRoles() : listTenantRoles(),
        realm === "platform" ? listPlatformPages() : listTenantPages(),
      ]);
      setRoles(rolesResult);
      setCatalogPages(pagesResult);
      setSelectedRoleId((current) => current || rolesResult[0]?.role_id || "");
    } catch (caught) {
      setError(errorMessage(caught));
    } finally {
      setLoading(false);
    }
  }, [realm]);

  useEffect(() => {
    void load();
  }, [load]);

  useEffect(() => {
    if (!selectedRoleId) {
      setPageAccess([]);
      setOriginalAccess([]);
      return;
    }
    const loadAccess = async () => {
      try {
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
  }, [realm, selectedRoleId]);

  const createModuleOptions = useMemo(() => {
    if (realm === "tenant" && principal?.principal_type === "tenant_user") {
      return [
        { value: "CORE", label: "Workspace" },
        ...principal.tenant.offerings.map((offering) => ({
          value: offering.code,
          label: offering.display_name,
        })),
      ];
    }
    const modules = [...new Set(catalogPages.map((page) => page.module).filter(Boolean))];
    return modules.map((value) => ({ value, label: humanModule(value) }));
  }, [catalogPages, principal, realm]);

  const offeringLabel = (code: string | null | undefined, fallbackModule: string) => {
    if (principal?.principal_type === "tenant_user" && code) {
      const offering = principal.tenant.offerings.find((item) => item.code === code);
      if (offering) return offering.display_name;
    }
    return humanModule(code || fallbackModule);
  };

  const moduleOptions = useMemo(() => {
    const options = new Map<string, string>();
    for (const entry of pageAccess) {
      const key = entry.page.offering_code || entry.page.module || "workspace";
      if (!options.has(key)) {
        options.set(key, offeringLabel(entry.page.offering_code, entry.page.module));
      }
    }
    return [...options.entries()].sort((left, right) => left[1].localeCompare(right[1]));
  }, [pageAccess, principal]);

  const grouped = useMemo(() => {
    const filtered = pageAccess.filter((entry) => {
      const moduleKey = entry.page.offering_code || entry.page.module || "workspace";
      if (moduleFilter !== "all" && moduleKey !== moduleFilter) return false;
      const haystack = `${entry.page.module} ${entry.page.page_name} ${entry.page.page_code} ${entry.page.route}`.toLowerCase();
      return haystack.includes(query.trim().toLowerCase());
    });
    const modules = new Map<string, PageAccess[]>();
    for (const entry of filtered) {
      const key = entry.page.offering_code || entry.page.module || "General";
      modules.set(key, [...(modules.get(key) ?? []), entry]);
    }
    return [...modules.entries()];
  }, [moduleFilter, pageAccess, query]);

  const setModuleAccess = (moduleKey: string, accessLevel: AccessLevel) => {
    setPageAccess((current) =>
      current.map((entry) => {
        const key = entry.page.offering_code || entry.page.module || "workspace";
        return key === moduleKey ? { ...entry, access_level: accessLevel } : entry;
      }),
    );
  };

  const handleCreateRole = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setSaving(true);
    setError(null);
    try {
      const payload = {
        role_name: roleForm.role_name,
        role_code: toRoleCode(roleForm.role_code || roleForm.role_name),
        description: roleForm.description || undefined,
        module_scope: roleForm.module_scope || undefined,
      };
      const role = realm === "platform" ? await createPlatformRole(payload) : await createTenantRole(payload);
      setRoleForm({ role_name: "", role_code: "", description: "", module_scope: "" });
      setModuleFilter("all");
      setCreateOpen(false);
      setNotice(`${role.role_name} created with code ${role.role_code}. Set page access below, then save.`);
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
      const role =
        realm === "platform"
          ? await updatePlatformRole(selectedRoleId, payload)
          : await updateTenantRole(selectedRoleId, payload);
      setEditOpen(false);
      setNotice(`${role.role_name} updated.`);
      await load();
      setSelectedRoleId(role.role_id);
    } catch (caught) {
      setError(errorMessage(caught));
    } finally {
      setSaving(false);
    }
  };

  const handleDeleteRole = async () => {
    if (!selectedRole || selectedRole.is_system) return;
    const confirmed = window.confirm(`Delete role “${selectedRole.role_name}”? Users must be unassigned first.`);
    if (!confirmed) return;
    setSaving(true);
    setError(null);
    try {
      if (realm === "platform") {
        await deletePlatformRole(selectedRole.role_id);
      } else {
        await deleteTenantRole(selectedRole.role_id);
      }
      setNotice(`${selectedRole.role_name} deleted.`);
      setSelectedRoleId("");
      await load();
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
    <section className={styles.page}>
      <header className={styles.header}>
        <div>
          <h1>Roles & Permissions</h1>
          <p className={styles.lede}>Define a role for one module, then set page access.</p>
        </div>
        <Button type="button" onClick={() => { setCreateOpen(true); setError(null); setRoleForm({ role_name: "", role_code: "", description: "", module_scope: "" }); }}>
          <Plus size={16} aria-hidden="true" />
          New Role
        </Button>
      </header>

      {error && <Alert tone="error">{error}</Alert>}
      {notice && <Alert tone="success">{notice}</Alert>}

      {loading ? (
        <div className={styles.loading}>Loading roles…</div>
      ) : (
        <div className={styles.layout}>
          <aside className={styles.roleList}>
            <header>
              <h2>Roles</h2>
              <small>{roles.filter((role) => role.is_active).length} active</small>
            </header>
            {roles.length === 0 && (
              <div className={styles.empty}>No roles yet. Create one to set None / View / Modify.</div>
            )}
            {roles.map((role) => (
              <button
                type="button"
                key={role.role_id}
                className={`${styles.roleCard} ${role.role_id === selectedRoleId ? styles.roleCardActive : ""}`}
                onClick={() => {
                  setSelectedRoleId(role.role_id);
                  setModuleFilter("all");
                  setQuery("");
                }}
              >
                <strong>{role.role_name}</strong>
                <span>
                  {role.role_code} · {role.module_scope ? humanModule(role.module_scope) : "All modules"} · {role.users_count} users
                </span>
              </button>
            ))}
          </aside>

          <section className={styles.detail}>
            {selectedRole ? (
              <>
                <div className={styles.detailHeader}>
                  <div>
                    <h2>{selectedRole.role_name}</h2>
                    <p>
                      Role code <strong>{selectedRole.role_code}</strong>
                      {" · "}
                      {selectedRole.description || "No description yet."}
                    </p>
                  </div>
                  <div className={styles.detailActions}>
                    <Button
                      type="button"
                      variant="secondary"
                      onClick={() => {
                        setRoleForm({
                          role_name: selectedRole.role_name,
                          role_code: selectedRole.role_code,
                          description: selectedRole.description ?? "",
                          module_scope: selectedRole.module_scope ?? "",
                        });
                        setEditOpen(true);
                        setError(null);
                      }}
                    >
                      <Pencil size={15} aria-hidden="true" />
                      Edit role
                    </Button>
                    <Button
                      type="button"
                      variant="secondary"
                      onClick={() => void handleDeleteRole()}
                      disabled={selectedRole.is_system || saving}
                    >
                      <Trash2 size={15} aria-hidden="true" />
                      Delete role
                    </Button>
                    <Button type="button" onClick={() => void handleSave()} loading={saving} disabled={!unsaved}>
                      Save changes
                    </Button>
                  </div>
                </div>
                <div className={styles.cards}>
                  <article><strong>{selectedRole.role_code}</strong><small>Role code</small></article>
                  <article><strong>{selectedRole.is_active ? "Active" : "Inactive"}</strong><small>Status</small></article>
                  <article><strong>{selectedRole.is_system ? "System" : "Custom"}</strong><small>Role type</small></article>
                  <article><strong>{selectedRole.users_count}</strong><small>Users assigned</small></article>
                </div>
                <div className={styles.matrixToolbar}>
                  {!selectedRole.module_scope && (
                  <label className={styles.moduleFilter}>
                    {realm === "tenant" ? "Module" : "Module"}
                    <select
                      value={moduleFilter}
                      onChange={(event) => setModuleFilter(event.target.value)}
                    >
                      <option value="all">All modules</option>
                      {moduleOptions.map(([value, label]) => (
                        <option key={value} value={value}>{label}</option>
                      ))}
                    </select>
                  </label>
                  )}
                  <InputField
                    id={`${realm}-permission-search`}
                    label="Search pages"
                    placeholder="Search pages in the selected module"
                    value={query}
                    onChange={(event) => setQuery(event.target.value)}
                    leadingIcon={<Search size={16} />}
                  />
                </div>
                <p className={styles.matrixHint}>
                  {selectedRole.module_scope
                    ? "This role is limited to the selected module."
                    : "Set None, View, or Modify for each page, then save."}
                </p>
                {grouped.map(([module, entries]) => (
                  <div className={styles.module} key={module}>
                    <div className={styles.moduleHeader}>
                      <h3>
                        {offeringLabel(entries[0]?.page.offering_code, module)} · {entries.length} pages
                      </h3>
                      <div className={styles.bulk}>
                        <button type="button" onClick={() => setModuleAccess(module, "none")}>None</button>
                        <button type="button" onClick={() => setModuleAccess(module, "view")}>View all</button>
                        <button type="button" onClick={() => setModuleAccess(module, "modify")}>Modify all</button>
                      </div>
                    </div>
                    {entries.map((entry) => (
                      <div className={styles.pageRow} key={entry.page.page_id}>
                        <div>
                          <strong>{entry.page.page_name}</strong>
                          <small>
                            {entry.page.page_code}
                            {entry.page.offering_code ? ` · ${entry.page.offering_code}` : " · always included"}
                          </small>
                        </div>
                        <div className={styles.segmented}>
                          {accessLevels.map((level) => (
                            <button
                              type="button"
                              key={level}
                              className={
                                entry.access_level === level
                                  ? `${styles.segmentActive} ${level === "view" ? styles.segmentView : ""} ${level === "none" ? styles.segmentNone : ""}`
                                  : ""
                              }
                              onClick={() =>
                                setPageAccess((current) =>
                                  current.map((item) =>
                                    item.page.page_id === entry.page.page_id
                                      ? { ...item, access_level: level }
                                      : item,
                                  ),
                                )
                              }
                            >
                              {level}
                            </button>
                          ))}
                        </div>
                      </div>
                    ))}
                  </div>
                ))}
                {grouped.length === 0 && (
                  <div className={styles.empty}>
                    {moduleFilter !== "all"
                      ? "No pages match this module. Choose another purchased offering from the dropdown."
                      : realm === "tenant"
                        ? "No entitled pages are available for this organisation yet."
                        : "No platform pages are registered yet."}
                  </div>
                )}
              </>
            ) : (
              <div className={styles.empty}>Create a role to start defining page access.</div>
            )}
          </section>
        </div>
      )}

      {createOpen && (
        <div className={styles.backdrop}>
          <form className={styles.dialog} onSubmit={handleCreateRole}>
            <div className={styles.dialogHeader}>
              <div>
                <h2>New role</h2>
                <p>Name the role and choose the module it can access.</p>
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
              <label className={styles.span2}>
                Module
                <select
                  required
                  value={roleForm.module_scope}
                  onChange={(event) => setRoleForm((current) => ({ ...current, module_scope: event.target.value }))}
                >
                  <option value="">Select a module</option>
                  {createModuleOptions.map((option) => (
                    <option key={option.value} value={option.value}>{option.label}</option>
                  ))}
                </select>
              </label>
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
          <form className={styles.dialog} onSubmit={handleEditRole}>
            <div className={styles.dialogHeader}>
              <div>
                <h2>Edit role</h2>
                <p>Update the name and description.</p>
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
