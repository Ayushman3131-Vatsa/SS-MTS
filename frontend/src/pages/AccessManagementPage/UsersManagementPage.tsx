import { Ban, Check, ChevronLeft, ChevronRight, CircleCheck, Copy, MoreHorizontal, Pencil, Plus, Search, UserPlus, X } from "lucide-react";
import { FormEvent, useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import { createPortal } from "react-dom";

import {
  assignPlatformUserRoles,
  assignTenantUserRoles,
  createPlatformUser,
  createTenantUser,
  listPlatformRoles,
  listPlatformUsers,
  listTenantRoles,
  listTenantUsers,
  updatePlatformUser,
  updateTenantUser,
  type PlatformUser,
  type Role,
  type TenantUser,
} from "../../features/access-management/api/access-management-api";
import { canModifyPage } from "../../entities/session/model/page-access";
import { useOptionalSession } from "../../entities/session/model/session-context";
import { getLoginErrorContent } from "../../features/auth/model/login-errors";
import { ApiError } from "../../shared/api/errors";
import { Alert } from "../../shared/ui/Alert/Alert";
import { Button } from "../../shared/ui/Button/Button";
import { InputField } from "../../shared/ui/InputField/InputField";
import { UserAvatar } from "../../shared/ui/UserAvatar/UserAvatar";
import { formatRoleLabel } from "../../shared/utils/user-display";
import { formatAccountEmailForDisplay } from "../../shared/utils/account-email";
import styles from "./AccessManagementPage.module.css";

export type AccessRealm = "platform" | "tenant";

interface UsersManagementPageProps {
  realm: AccessRealm;
}

interface UserFormState {
  display_name: string;
  email: string;
  employee_id: string;
  username: string;
  roleIds: string[];
  status: "Active" | "Inactive";
}

interface CreatedCredentials {
  name: string;
  email: string;
  username: string;
  temporary_password: string;
}

const emptyForm = (): UserFormState => ({
  display_name: "",
  email: "",
  employee_id: "",
  username: "",
  roleIds: [],
  status: "Active",
});

const resolveDisplayName = (displayName: string, username: string) =>
  displayName.trim() || username.trim();

const formatLogin = (value: string | null) => {
  if (!value) return "Never";
  return new Date(value).toLocaleString();
};

interface MenuPosition {
  top: number;
  left: number;
}

const MENU_GAP = 6;
const VIEWPORT_PAD = 8;
const MENU_EST_WIDTH = 200;
const MENU_EST_HEIGHT = 88;
const DEFAULT_PAGE_SIZE = 10;
const PAGE_SIZE_OPTIONS = [10, 25, 50] as const;

const computeMenuPosition = (
  button: HTMLButtonElement,
  menuWidth: number,
  menuHeight: number,
): MenuPosition => {
  const rect = button.getBoundingClientRect();
  const vw = window.innerWidth;
  const vh = window.innerHeight;

  let top = rect.bottom + MENU_GAP;
  if (top + menuHeight > vh - VIEWPORT_PAD) {
    top = rect.top - MENU_GAP - menuHeight;
  }
  top = Math.max(VIEWPORT_PAD, Math.min(top, vh - menuHeight - VIEWPORT_PAD));

  let left = rect.right - menuWidth;
  if (left < VIEWPORT_PAD) {
    left = rect.left;
  }
  left = Math.max(VIEWPORT_PAD, Math.min(left, vw - menuWidth - VIEWPORT_PAD));

  return { top, left };
};

export const UsersManagementPage = ({ realm }: UsersManagementPageProps) => {
  const principal = useOptionalSession()?.principal;
  const canModify = canModifyPage(principal, realm === "platform" ? "/platform/users" : "/app/users");
  const [platformUsers, setPlatformUsers] = useState<PlatformUser[]>([]);
  const [tenantUsers, setTenantUsers] = useState<TenantUser[]>([]);
  const [roles, setRoles] = useState<Role[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const [roleFilter, setRoleFilter] = useState("all");
  const [statusFilter, setStatusFilter] = useState("all");
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState<number>(DEFAULT_PAGE_SIZE);
  const [dialog, setDialog] = useState<"create" | "edit" | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [menuId, setMenuId] = useState<string | null>(null);
  const [menuPosition, setMenuPosition] = useState<MenuPosition | null>(null);
  const [form, setForm] = useState<UserFormState>(emptyForm);
  const [createdCredentials, setCreatedCredentials] = useState<CreatedCredentials | null>(null);
  const [copiedField, setCopiedField] = useState<string | null>(null);
  const menuButtonRef = useRef<HTMLButtonElement | null>(null);
  const menuPanelRef = useRef<HTMLDivElement | null>(null);

  const closeMenu = useCallback(() => {
    setMenuId(null);
    setMenuPosition(null);
    menuButtonRef.current = null;
  }, []);

  const openMenu = useCallback((id: string, button: HTMLButtonElement) => {
    menuButtonRef.current = button;
    setMenuPosition(computeMenuPosition(button, MENU_EST_WIDTH, MENU_EST_HEIGHT));
    setMenuId(id);
  }, []);

  const toggleMenu = useCallback((id: string, button: HTMLButtonElement) => {
    if (menuId === id) {
      closeMenu();
      return;
    }
    openMenu(id, button);
  }, [closeMenu, menuId, openMenu]);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      if (realm === "platform") {
        const [usersResult, rolesResult] = await Promise.all([listPlatformUsers(), listPlatformRoles()]);
        setPlatformUsers(usersResult);
        setRoles(rolesResult);
      } else {
        const [usersResult, rolesResult] = await Promise.all([listTenantUsers(), listTenantRoles()]);
        setTenantUsers(usersResult);
        setRoles(rolesResult);
      }
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : getLoginErrorContent(caught).message);
    } finally {
      setLoading(false);
    }
  }, [realm]);

  useEffect(() => {
    void load();
  }, [load]);

  useLayoutEffect(() => {
    if (!menuId) return;

    const updatePosition = () => {
      const button = menuButtonRef.current;
      if (!button) return;
      const panel = menuPanelRef.current;
      const width = panel?.offsetWidth ?? MENU_EST_WIDTH;
      const height = panel?.offsetHeight ?? MENU_EST_HEIGHT;
      setMenuPosition(computeMenuPosition(button, width, height));
    };

    updatePosition();
    window.addEventListener("scroll", updatePosition, true);
    window.addEventListener("resize", updatePosition);
    return () => {
      window.removeEventListener("scroll", updatePosition, true);
      window.removeEventListener("resize", updatePosition);
    };
  }, [menuId]);

  useEffect(() => {
    if (!menuId) return;

    const handlePointerDown = (event: PointerEvent) => {
      const target = event.target;
      if (!(target instanceof Node)) return;
      if (menuButtonRef.current?.contains(target)) return;
      if (menuPanelRef.current?.contains(target)) return;
      closeMenu();
    };

    document.addEventListener("pointerdown", handlePointerDown, true);
    return () => {
      document.removeEventListener("pointerdown", handlePointerDown, true);
    };
  }, [closeMenu, menuId]);

  useEffect(() => {
    setPage(1);
    closeMenu();
  }, [closeMenu, query, roleFilter, statusFilter, pageSize]);

  const rows = useMemo(() => {
    if (realm === "platform") {
      return platformUsers
        .filter((user) => {
          const haystack = `${user.name} ${user.username} ${user.email} ${user.admin_id}`.toLowerCase();
          const matchesQuery = haystack.includes(query.trim().toLowerCase());
          const matchesRole =
            roleFilter === "all" || user.roles.some((role) => role.role_id === roleFilter);
          const matchesStatus =
            statusFilter === "all" ||
            (statusFilter === "Active" && user.is_active !== false) ||
            (statusFilter === "Inactive" && user.is_active === false);
          return matchesQuery && matchesRole && matchesStatus;
        })
        .map((user) => ({
          id: user.admin_id,
          name: user.name,
          username: user.username,
          email: user.email,
          employeeId: user.employee_id ?? null,
          roles: user.roles.map((role) => role.role_name),
          roleIds: user.roles.map((role) => role.role_id),
          status: (user.is_active === false ? "Inactive" : "Active") as "Active" | "Inactive",
          lastLogin: user.last_login_at,
          privileged: user.roles.length > 0,
          version: 1,
        }));
    }
    return tenantUsers
      .filter((user) => {
        const haystack = `${user.name} ${user.username} ${user.email} ${user.user_id} ${user.employee_id ?? ""}`.toLowerCase();
        const matchesQuery = haystack.includes(query.trim().toLowerCase());
        const matchesRole =
          roleFilter === "all" ||
          user.roles.includes(roles.find((role) => role.role_id === roleFilter)?.role_name ?? "") ||
          user.role === roles.find((role) => role.role_id === roleFilter)?.role_name;
        const matchesStatus = statusFilter === "all" || user.status === statusFilter;
        return matchesQuery && matchesRole && matchesStatus;
      })
      .map((user) => ({
        id: user.user_id,
        name: user.name,
        username: user.username,
        email: user.email,
        employeeId: user.employee_id,
        roles: user.roles.length > 0 ? user.roles : user.role === "Unassigned" ? [] : [user.role],
        roleIds: roles.filter((role) => (user.roles.length > 0 ? user.roles : user.role === "Unassigned" ? [] : [user.role]).includes(role.role_name)).map((role) => role.role_id),
        status: user.status,
        lastLogin: user.last_login_at,
        privileged: (user.roles.length > 0 ? user.roles : [user.role]).some((role) =>
          /admin/i.test(role),
        ),
        version: user.version,
      }));
  }, [platformUsers, query, realm, roleFilter, roles, statusFilter, tenantUsers]);

  const totalRows = rows.length;
  const totalPages = Math.max(1, Math.ceil(totalRows / pageSize));
  const currentPage = Math.min(page, totalPages);
  const pageStart = totalRows === 0 ? 0 : (currentPage - 1) * pageSize + 1;
  const pageEnd = Math.min(currentPage * pageSize, totalRows);
  const paginatedRows = useMemo(
    () => rows.slice((currentPage - 1) * pageSize, currentPage * pageSize),
    [currentPage, pageSize, rows],
  );

  const stats = useMemo(() => {
    const source = realm === "platform"
      ? platformUsers.map((user) => ({
          status: user.is_active === false ? "Inactive" : "Active",
          privileged: user.roles.length > 0,
        }))
      : tenantUsers.map((user) => ({
          status: user.status,
          privileged: (user.roles.length > 0 ? user.roles : [user.role]).some((role) => /admin/i.test(role)),
        }));
    return {
      total: source.length,
      active: source.filter((user) => user.status === "Active").length,
      inactive: source.filter((user) => user.status !== "Active").length,
      privileged: source.filter((user) => user.privileged).length,
    };
  }, [platformUsers, realm, tenantUsers]);

  const openCreate = () => {
    if (!canModify) return;
    setSelectedId(null);
    setForm(emptyForm());
    setDialog("create");
    setError(null);
  };

  const openEdit = (id: string) => {
    if (!canModify) return;
    const row = rows.find((item) => item.id === id);
    if (!row) return;
    closeMenu();
    setSelectedId(id);
    setForm({
      display_name: row.name,
      email: row.email,
      username: row.username,
      employee_id: row.employeeId ?? "",
      roleIds: row.roleIds,
      status: row.status,
    });
    setDialog("edit");
  };

  const closeDialog = () => {
    setDialog(null);
  };

  const copyValue = async (field: string, value: string) => {
    try {
      await navigator.clipboard.writeText(value);
      setCopiedField(field);
      window.setTimeout(() => setCopiedField((current) => (current === field ? null : current)), 1600);
    } catch {
      setError("Could not copy to clipboard.");
    }
  };

  const handleToggleStatus = async (id: string) => {
    if (!canModify) return;
    const row = rows.find((item) => item.id === id);
    if (!row) return;
    if (principal?.principal_id === id) {
      setError("You cannot deactivate your own account.");
      closeMenu();
      return;
    }
    const nextStatus = row.status === "Active" ? "Inactive" : "Active";
    const confirmed = window.confirm(
      nextStatus === "Inactive"
        ? `Deactivate ${row.name}? They will not be able to sign in until reactivated.`
        : `Reactivate ${row.name}? They will be able to sign in again.`,
    );
    if (!confirmed) return;
    closeMenu();
    setSaving(true);
    setError(null);
    setNotice(null);
    try {
      if (realm === "platform") {
        await updatePlatformUser(id, { is_active: nextStatus === "Active" });
      } else {
        const current = tenantUsers.find((user) => user.user_id === id);
        await updateTenantUser(id, {
          status: nextStatus,
          version: current?.version ?? row.version,
        });
      }
      setNotice(nextStatus === "Inactive" ? `${row.name} was deactivated.` : `${row.name} was reactivated.`);
      await load();
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : getLoginErrorContent(caught).message);
    } finally {
      setSaving(false);
    }
  };

  const toggleRole = (roleId: string) => {
    setForm((current) => ({
      ...current,
      roleIds: current.roleIds.includes(roleId)
        ? current.roleIds.filter((id) => id !== roleId)
        : [...current.roleIds, roleId],
    }));
  };

  const handleSaveUser = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!canModify) {
      setError("Modify permission required to save user details.");
      return;
    }
    setSaving(true);
    setError(null);
    setNotice(null);
    try {
      if (dialog === "create") {
        const name = resolveDisplayName(form.display_name, form.username);
        if (realm === "platform") {
          const created = await createPlatformUser({
            name,
            email: form.email.trim() || undefined,
            username: form.username.trim(),
            employee_id: form.employee_id || undefined,
            role_ids: form.roleIds,
          });
          if (created.temporary_password) {
            setCreatedCredentials({
              name: created.name,
              email: created.email,
              username: created.username,
              temporary_password: created.temporary_password,
            });
          }
        } else {
          const created = await createTenantUser({
            name,
            employee_id: form.employee_id || undefined,
            username: form.username.trim(),
            email: form.email.trim() || undefined,
            role_ids: form.roleIds,
          });
          if (created.temporary_password) {
            setCreatedCredentials({
              name: created.name,
              email: created.email,
              username: created.username,
              temporary_password: created.temporary_password,
            });
          }
        }
        setNotice("User created. Share the temporary password now — it will not be shown again.");
      } else if (dialog === "edit" && selectedId) {
        const name = resolveDisplayName(form.display_name, form.username);
        if (realm === "platform") {
          await updatePlatformUser(selectedId, {
            name,
            employee_id: form.employee_id || null,
          });
          await assignPlatformUserRoles(selectedId, form.roleIds);
        } else {
          const current = tenantUsers.find((user) => user.user_id === selectedId);
          await updateTenantUser(selectedId, {
            name,
            employee_id: form.employee_id || null,
            status: form.status,
            version: current?.version ?? 1,
          });
          await assignTenantUserRoles(selectedId, form.roleIds);
        }
        setNotice("User details saved.");
      }
      closeDialog();
      await load();
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : getLoginErrorContent(caught).message);
    } finally {
      setSaving(false);
    }
  };

  return (
    <section className={styles.page}>
      <header className={styles.header}>
        <div>
          <h1>Users</h1>
          <p className={styles.lede}>Create accounts and assign roles from User Access Management.</p>
        </div>
        {canModify && (
          <Button type="button" onClick={openCreate}>
            <Plus size={16} aria-hidden="true" />
            New User
          </Button>
        )}
      </header>

      <div className={styles.stats}>
        <article className={styles.stat}><strong>{stats.total}</strong><small>Total users</small></article>
        <article className={styles.stat}><strong>{stats.active}</strong><small>Active</small></article>
        <article className={styles.stat}><strong>{stats.inactive}</strong><small>Inactive</small></article>
        <article className={styles.stat}><strong>{stats.privileged}</strong><small>Privileged</small></article>
      </div>

      <div className={styles.toolbar}>
        <InputField
          id={`${realm}-user-search`}
          label="Search"
          placeholder="Search by name, username, or email"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          leadingIcon={<Search size={16} />}
        />
        <label>
          Filter by role
          <select value={roleFilter} onChange={(event) => setRoleFilter(event.target.value)}>
            <option value="all">All roles</option>
            {roles.map((role) => (
              <option key={role.role_id} value={role.role_id}>{role.role_name}</option>
            ))}
          </select>
        </label>
        <label>
          Filter by status
          <select value={statusFilter} onChange={(event) => setStatusFilter(event.target.value)}>
            <option value="all">All status</option>
            <option value="Active">Active</option>
            <option value="Inactive">Inactive</option>
          </select>
        </label>
      </div>

      {error && <Alert tone="error">{error}</Alert>}
      {notice && <Alert tone="success">{notice}</Alert>}

      <div className={styles.panel}>
        {loading ? (
          <div className={styles.loading}>Loading users…</div>
        ) : (
          <div className={styles.tableWrap}>
            <table>
              <thead>
                <tr>
                  <th>User</th>
                  <th>Email</th>
                  <th>Employee ID</th>
                  <th>Roles</th>
                  <th>Status</th>
                  <th>Last login</th>
                  <th className={styles.actionsHeader}>Actions</th>
                </tr>
              </thead>
              <tbody>
                {paginatedRows.map((user) => (
                  <tr key={user.id}>
                    <td>
                      <div className={styles.identity}>
                        <UserAvatar name={user.name} size="md" />
                        <div className={styles.identityText}>
                          <span className={styles.identityName}>{user.name}</span>
                          <span className={styles.identityMeta}>{user.username}</span>
                        </div>
                      </div>
                    </td>
                    <td>
                      {formatAccountEmailForDisplay(user.email) ? (
                        <a
                          className={styles.emailCell}
                          href={`mailto:${formatAccountEmailForDisplay(user.email)}`}
                        >
                          {formatAccountEmailForDisplay(user.email)}
                        </a>
                      ) : (
                        <span className={styles.emailCellMuted}>—</span>
                      )}
                    </td>
                    <td>{user.employeeId || "—"}</td>
                    <td>
                      <div className={styles.roles}>
                        {user.roles.length === 0 ? (
                          <span className={styles.roleChipMuted}>No role</span>
                        ) : (
                          user.roles.map((role) => (
                            <span className={styles.roleChip} key={role}>{formatRoleLabel(role)}</span>
                          ))
                        )}
                      </div>
                    </td>
                    <td>
                      <span
                        className={`${styles.status} ${user.status === "Active" ? styles.statusActive : ""}`}
                      >
                        <i
                          className={`${styles.dot} ${user.status === "Inactive" ? styles.dotInactive : ""}`}
                          aria-hidden="true"
                        />
                        {user.status}
                      </span>
                    </td>
                    <td>{formatLogin(user.lastLogin)}</td>
                    <td className={styles.actionsCell}>
                      {canModify ? (
                        <div className={styles.menuWrap}>
                          <button
                            type="button"
                            className={styles.iconButton}
                            aria-label={`Actions for ${user.name}`}
                            aria-expanded={menuId === user.id}
                            aria-haspopup="menu"
                            title="More actions"
                            onClick={(event) => toggleMenu(user.id, event.currentTarget)}
                          >
                            <MoreHorizontal size={18} aria-hidden="true" />
                          </button>
                        </div>
                      ) : (
                        <span className={styles.emailCellMuted}>—</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            {rows.length === 0 && <div className={styles.empty}>No users match the current filters.</div>}
            {rows.length > 0 && (
              <nav className={styles.pagination} aria-label="Users table pagination">
                <span className={styles.paginationSummary}>
                  Showing {pageStart}–{pageEnd} of {totalRows} users
                </span>
                <label className={styles.pageSizeControl}>
                  Rows per page
                  <select
                    value={pageSize}
                    onChange={(event) => setPageSize(Number(event.target.value))}
                    aria-label="Rows per page"
                  >
                    {PAGE_SIZE_OPTIONS.map((size) => (
                      <option key={size} value={size}>{size}</option>
                    ))}
                  </select>
                </label>
                <div className={styles.paginationActions}>
                  <Button
                    type="button"
                    variant="secondary"
                    disabled={currentPage <= 1}
                    onClick={() => setPage((value) => Math.max(1, value - 1))}
                    aria-label="Previous page"
                  >
                    <ChevronLeft size={15} aria-hidden="true" />
                    Previous
                  </Button>
                  <span className={styles.pageIndicator}>
                    Page {currentPage} of {totalPages}
                  </span>
                  <Button
                    type="button"
                    variant="secondary"
                    disabled={currentPage >= totalPages}
                    onClick={() => setPage((value) => Math.min(totalPages, value + 1))}
                    aria-label="Next page"
                  >
                    Next
                    <ChevronRight size={15} aria-hidden="true" />
                  </Button>
                </div>
              </nav>
            )}
          </div>
        )}
      </div>

      {dialog && (
        <div className={styles.backdrop} role="presentation">
          <form
            className={styles.dialog}
            onSubmit={handleSaveUser}
          >
            <div className={styles.dialogHeader}>
              <div>
                <h2>{dialog === "create" ? "New user" : "Edit user"}</h2>
                <p>
                  {dialog === "create"
                    ? "A temporary password is generated after you save."
                    : "Update profile and roles."}
                </p>
              </div>
              <button type="button" className={styles.close} onClick={closeDialog} aria-label="Close">
                <X size={18} />
              </button>
            </div>
            {error && <Alert tone="error">{error}</Alert>}

            <div className={styles.formGrid}>
              <div className={styles.span2}>
                <InputField
                  id={`${realm}-username`}
                  label="Username"
                  value={form.username}
                  onChange={(event) => setForm((current) => ({ ...current, username: event.target.value }))}
                  required
                  disabled={dialog === "edit"}
                  autoComplete="off"
                  hint={
                    dialog === "edit"
                      ? "Usernames cannot be changed after the user is created."
                      : "Unique. Letters, numbers, dots, hyphens, or underscores."
                  }
                />
              </div>
              <div className={styles.span2}>
                <InputField
                  id={`${realm}-display-name`}
                  label="Display name"
                  value={form.display_name}
                  onChange={(event) => setForm((current) => ({ ...current, display_name: event.target.value }))}
                  hint="Optional. Defaults to the username when left blank."
                />
              </div>
              <div className={styles.span2}>
                <InputField
                  id={`${realm}-work-email`}
                  label="Work email"
                  type="email"
                  value={form.email}
                  onChange={(event) => setForm((current) => ({ ...current, email: event.target.value }))}
                  disabled={dialog === "edit"}
                  hint={dialog === "create" ? "Optional. A placeholder is generated when left blank." : undefined}
                />
              </div>
              <div className={styles.span2}>
                <InputField
                  id={`${realm}-employee-id`}
                  label="Employee ID"
                  value={form.employee_id}
                  onChange={(event) => setForm((current) => ({ ...current, employee_id: event.target.value }))}
                  hint="Optional, must be unique"
                />
              </div>
              {dialog === "edit" && realm === "tenant" && (
                <label className={styles.span2}>
                  Status
                  <select
                    value={form.status}
                    onChange={(event) =>
                      setForm((current) => ({ ...current, status: event.target.value as "Active" | "Inactive" }))
                    }
                  >
                    <option value="Active">Active</option>
                    <option value="Inactive">Inactive</option>
                  </select>
                </label>
              )}
            </div>

            <div className={styles.span2} style={{ marginTop: "0.9rem" }}>
              <p className={styles.roleSectionLabel}>Roles <span>(optional)</span></p>
              <div className={styles.rolePicker}>
                {roles.map((role) => (
                  <label key={role.role_id}>
                    <input
                      type="checkbox"
                      checked={form.roleIds.includes(role.role_id)}
                      onChange={() => toggleRole(role.role_id)}
                    />
                    {role.role_name}
                    {role.is_system ? " · system" : ""}
                  </label>
                ))}
                {roles.length === 0 && (
                  <span className={styles.rolePickerEmpty}>
                    No roles yet. Users cannot sign in until a role is assigned.
                  </span>
                )}
              </div>
            </div>

            <div className={styles.dialogActions}>
              <Button type="button" variant="secondary" onClick={closeDialog} disabled={saving}>
                Cancel
              </Button>
              <Button type="submit" loading={saving} loadingLabel="Saving…">
                <UserPlus size={16} aria-hidden="true" />
                {dialog === "create" ? "Create user" : "Save changes"}
              </Button>
            </div>
          </form>
        </div>
      )}

      {createdCredentials && (
        <div className={styles.backdrop} role="presentation">
          <div className={styles.dialog}>
            <div className={styles.dialogHeader}>
              <div>
                <h2>Share sign-in details</h2>
                <p>Copy these now. The temporary password is shown only once.</p>
              </div>
              <button
                type="button"
                className={styles.close}
                onClick={() => { setCreatedCredentials(null); setCopiedField(null); }}
                aria-label="Close"
              >
                <X size={18} />
              </button>
            </div>
            <dl className={styles.credentialList}>
              {formatAccountEmailForDisplay(createdCredentials.email) ? (
                <div>
                  <dt>Work email</dt>
                  <dd>
                    <code>{formatAccountEmailForDisplay(createdCredentials.email)}</code>
                    <button
                      type="button"
                      onClick={() => void copyValue("email", formatAccountEmailForDisplay(createdCredentials.email)!)}
                    >
                      {copiedField === "email" ? <Check size={14} /> : <Copy size={14} />}
                      {copiedField === "email" ? "Copied" : "Copy"}
                    </button>
                  </dd>
                </div>
              ) : null}
              <div>
                <dt>Username</dt>
                <dd>
                  <code>{createdCredentials.username}</code>
                  <button type="button" onClick={() => void copyValue("username", createdCredentials.username)}>
                    {copiedField === "username" ? <Check size={14} /> : <Copy size={14} />}
                    {copiedField === "username" ? "Copied" : "Copy"}
                  </button>
                </dd>
              </div>
              <div>
                <dt>Temporary password</dt>
                <dd>
                  <code>{createdCredentials.temporary_password}</code>
                  <button type="button" onClick={() => void copyValue("password", createdCredentials.temporary_password)}>
                    {copiedField === "password" ? <Check size={14} /> : <Copy size={14} />}
                    {copiedField === "password" ? "Copied" : "Copy"}
                  </button>
                </dd>
              </div>
            </dl>
            <p className={styles.credentialHint}>
              {createdCredentials.name} can sign in with{" "}
              {formatAccountEmailForDisplay(createdCredentials.email)
                ? "work email or username"
                : "username only"}
              , then must change this password on first sign-in.
            </p>
            <div className={styles.dialogActions}>
              <Button type="button" onClick={() => { setCreatedCredentials(null); setCopiedField(null); }}>
                Done
              </Button>
            </div>
          </div>
        </div>
      )}

      {menuId && menuPosition && typeof document !== "undefined" && createPortal(
        (() => {
          const activeUser = rows.find((user) => user.id === menuId);
          if (!activeUser) return null;
          return (
            <div
              ref={menuPanelRef}
              className={styles.menuPortal}
              role="menu"
              style={{
                top: menuPosition.top,
                left: menuPosition.left,
              }}
            >
              <button type="button" role="menuitem" onClick={() => openEdit(activeUser.id)}>
                <Pencil size={14} aria-hidden="true" />
                Edit user
              </button>
              <button
                type="button"
                role="menuitem"
                className={activeUser.status === "Active" ? styles.menuDanger : undefined}
                onClick={() => void handleToggleStatus(activeUser.id)}
                disabled={principal?.principal_id === activeUser.id || saving}
              >
                {activeUser.status === "Active" ? (
                  <Ban size={14} aria-hidden="true" />
                ) : (
                  <CircleCheck size={14} aria-hidden="true" />
                )}
                {activeUser.status === "Active" ? "Deactivate user" : "Reactivate user"}
              </button>
            </div>
          );
        })(),
        document.body,
      )}
    </section>
  );
};
