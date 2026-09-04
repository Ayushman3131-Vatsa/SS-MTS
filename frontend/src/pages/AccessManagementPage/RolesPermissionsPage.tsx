import { ArrowLeft, ChevronLeft, ChevronRight, Eye, MoreHorizontal, Pencil, Plus, Search, Shield, X } from "lucide-react";
import { FormEvent, useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { useSearchParams } from "react-router-dom";

import {
  createPlatformRole,
  createTenantRole,
  listPlatformPageAccess,
  listPlatformRoles,
  listTenantPageAccess,
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
import { defaultRolesApi } from "../../features/default-role-management/api/default-roles-api";
import type { DefaultRoleListItem } from "../../features/default-role-management/model/default-roles";
import { offeringsApi } from "../../features/offering-management/api/offerings-api";
import type { OfferingCatalogItem } from "../../features/offering-management/model/offerings";
import { canModifyPage } from "../../entities/session/model/page-access";
import { useOptionalSession } from "../../entities/session/model/session-context";
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

// NEW: "Created" column formatter for the roles table.
const formatCreatedDate = (value: string) =>
  new Date(value).toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" });

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

// NEW: rows in the merged "All Role Types" list are tagged with which system they came
// from (a plain platform role vs. a tenant default-role template) so per-row rendering
// and the permission studio can branch correctly without relying on the page-level filter.
type RoleRow = Role & { _kind?: "platform" | "tenant" };

const emptyRoleForm = {
  role_name: "",
  role_code: "",
  description: "",
  module_scope: "",
  role_type: "platform" as "platform" | "tenant",
};

// NEW: row-actions menu positioning, mirrored from UsersManagementPage so the roles
// table's "..." menu behaves the same way (flips above the fold, portal-rendered).
interface MenuPosition {
  top: number;
  left: number;
}
const MENU_GAP = 6;
const VIEWPORT_PAD = 8;
const MENU_EST_WIDTH = 190;
const MENU_EST_HEIGHT = 48;
const DEFAULT_PAGE_SIZE = 10;
const PAGE_SIZE_OPTIONS = [10, 25, 50] as const;

const computeMenuPosition = (button: HTMLButtonElement, menuWidth: number, menuHeight: number): MenuPosition => {
  const rect = button.getBoundingClientRect();
  const vw = window.innerWidth;
  const vh = window.innerHeight;

  let top = rect.bottom + MENU_GAP;
  if (top + menuHeight > vh - VIEWPORT_PAD) {
    top = rect.top - MENU_GAP - menuHeight;
  }
  top = Math.max(VIEWPORT_PAD, Math.min(top, vh - menuHeight - VIEWPORT_PAD));

  let left = rect.right - menuWidth;
  if (left < VIEWPORT_PAD) left = rect.left;
  left = Math.max(VIEWPORT_PAD, Math.min(left, vw - menuWidth - VIEWPORT_PAD));

  return { top, left };
};

export const RolesPermissionsPage = ({ realm }: RolesPermissionsPageProps) => {
  const principal = useOptionalSession()?.principal;
  const [searchParams, setSearchParams] = useSearchParams();
  // NEW: "type" is absent -> "all" (merged Platform + Tenant listing, the default landing
  // view); "platform" / "tenant" narrow to just that kind. The tenant realm (workspace app)
  // only ever deals in its own tenant roles.
  const typeParam = searchParams.get("type");
  const roleKind: "platform" | "tenant" | "all" =
    realm === "tenant" ? "tenant" : typeParam === "tenant" ? "tenant" : typeParam === "platform" ? "platform" : "all";
  const offeringId = roleKind === "tenant" ? (searchParams.get("offering_id") ?? "") : "";
  const [roles, setRoles] = useState<RoleRow[]>([]);
  const [selectedRoleId, setSelectedRoleId] = useState("");
  // NEW: which system the currently-open role belongs to, used only while roleKind is "all"
  // (the merged list) so the permission studio knows whether to call the platform-role APIs
  // or the tenant default-role-template APIs for the role the user clicked into.
  const [viewingKind, setViewingKind] = useState<"platform" | "tenant">("platform");
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
  const [createOpen, setCreateOpen] = useState(false);
  const [editOpen, setEditOpen] = useState(false);
  const [roleForm, setRoleForm] = useState(emptyRoleForm);

  // NEW: list vs. detail navigation. The roles table is now the landing screen ("Role Search
  // Screen"); clicking "View" on a row (or finishing "Create Role") drops into the existing
  // permission studio below. "Back to roles" returns to the table.
  const [view, setView] = useState<"list" | "detail">("list");
  const [roleQuery, setRoleQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState<"all" | "active" | "inactive">("all");
  const [rolePage, setRolePage] = useState(1);
  const [rolePageSize, setRolePageSize] = useState<number>(DEFAULT_PAGE_SIZE);
  const [menuId, setMenuId] = useState<string | null>(null);
  const [menuPosition, setMenuPosition] = useState<MenuPosition | null>(null);
  const menuButtonRef = useRef<HTMLButtonElement | null>(null);
  const menuPanelRef = useRef<HTMLDivElement | null>(null);

  const closeMenu = useCallback(() => {
    setMenuId(null);
    setMenuPosition(null);
    menuButtonRef.current = null;
  }, []);

  const toggleMenu = useCallback(
    (id: string, button: HTMLButtonElement) => {
      if (menuId === id) {
        closeMenu();
        return;
      }
      menuButtonRef.current = button;
      setMenuPosition(computeMenuPosition(button, MENU_EST_WIDTH, MENU_EST_HEIGHT));
      setMenuId(id);
    },
    [closeMenu, menuId],
  );

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
    return () => document.removeEventListener("pointerdown", handlePointerDown, true);
  }, [closeMenu, menuId]);

  // NEW: kind of the role currently open in the studio. For a single-kind list
  // (roleKind "platform" or "tenant") this always matches roleKind; in the merged "all"
  // list it follows whichever row was opened (see openRole / openEditFromRow below).
  const effectiveDetailKind: "platform" | "tenant" =
    realm === "tenant" ? "tenant" : roleKind === "all" ? viewingKind : roleKind === "tenant" ? "tenant" : "platform";
  const isTenantTemplate = realm === "platform" && effectiveDetailKind === "tenant";
  const canModify = canModifyPage(principal, realm === "platform" ? "/platform/roles" : "/app/roles");
  const licensedOfferings = useMemo(
    () => (principal?.principal_type === "tenant_user" ? principal.tenant.offerings : []),
    [principal],
  );
  // NEW: the server-scoped Offering dropdown (drives a URL param + refetch) only makes
  // sense once we've narrowed to a single kind of tenant role; the merged "all" list uses
  // the client-side offering filter below instead, same as the pure-platform list does.
  const showOfferingFilter = realm === "tenant" || roleKind === "tenant";
  const selectedOffering =
    realm === "tenant"
      ? licensedOfferings.find((item) => item.offering_id === offeringId || item.code === offeringId)
      : offerings.find((item) => item.offering_id === offeringId || item.code === offeringId);
  const moduleRoles = useMemo(() => {
    if (realm === "tenant" || (realm === "platform" && roleKind === "tenant")) {
      if (!offeringId || offeringId === "all") {
        return roles;
      }
      if (offeringId === "core") {
        return roles.filter(
          (role) =>
            !role.module_scope ||
            role.module_scope === "CORE" ||
            role.module_scope === "user_access_management" ||
            role.module_scope === "tenant_administration",
        );
      }
      if (offeringId === "user_access_management") {
        return roles.filter(
          (role) =>
            role.module_scope === "user_access_management" ||
            role.module_scope === "USER_ACCESS_MANAGEMENT",
        );
      }
      if (offeringId === "tenant_administration") {
        return roles.filter(
          (role) =>
            role.module_scope === "tenant_administration" ||
            role.module_scope === "TENANT_ADMINISTRATION" ||
            role.module_scope === "CORE" ||
            !role.module_scope,
        );
      }
      const catalog = realm === "tenant" ? licensedOfferings : offerings;
      const matched = catalog.find(
        (o) => o.code === offeringId || o.offering_id === offeringId,
      );
      const targetCode = matched?.code ?? offeringId;
      const targetId = matched?.offering_id;

      return roles.filter((role) => {
        const scope = role.module_scope || "";
        return (
          scope === targetCode ||
          (targetId && scope === targetId) ||
          scope === offeringId
        );
      });
    }
    return roles;
  }, [licensedOfferings, offeringId, offerings, realm, roleKind, roles]);
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

  const isRoleTenant = useCallback(
    (role: RoleRow) => (role._kind ? role._kind === "tenant" : realm === "tenant" || roleKind === "tenant"),
    [realm, roleKind],
  );

  // NEW: "Offering" column value for a row in the roles table.
  const offeringLabelForRole = useCallback(
    (role: RoleRow) => {
      const scope = role.module_scope || "";
      const isTenant = isRoleTenant(role);

      if (scope === "user_access_management") return "User Access Management";
      if (scope === "tenant_administration") return "Tenant Administration";
      if (scope === "platform_administration") return "Platform Administration";

      // If it matches a catalog offering display name
      const catalog = realm === "tenant" ? licensedOfferings : offerings;
      const matchedOffering = catalog.find((item) => item.code === scope || item.offering_id === scope);
      if (matchedOffering) {
        return matchedOffering.display_name;
      }

      if (isTenant) {
        if (scope === "CORE" || !scope) return "Tenant Administration";
        return humanModule(scope);
      }

      if (scope === "platform" || scope === "PLATFORM" || scope === "CORE" || !scope) {
        return "Platform Administration";
      }

      return humanModule(scope);
    },
    [isRoleTenant, licensedOfferings, offerings, realm],
  );

  // NEW: plain platform roles (and, in the merged "all" list, tenant default-role
  // templates too) don't have server-side offering scoping via a URL param, so the
  // "Offering" filter is derived client-side and applied the same way.
  const showClientOfferingFilter = realm === "platform" && (roleKind === "platform" || roleKind === "all");
  const [offeringFilterValue, setOfferingFilterValue] = useState("all");
  const availableOfferingLabels = useMemo(() => {
    if (!showClientOfferingFilter) return [];
    return [...new Set(moduleRoles.map((role) => offeringLabelForRole(role)))].sort();
  }, [moduleRoles, offeringLabelForRole, showClientOfferingFilter]);

  // NEW: roles-table rows — client-side search + type/offering/status filters over the
  // currently loaded role set (platform roles, tenant/tenant-default roles scoped by
  // the Offering control, or the merged "all" set).
  const roleRows = useMemo(() => {
    const needle = roleQuery.trim().toLowerCase();
    return moduleRoles.filter((role) => {
      const haystack = `${role.role_name} ${role.role_code} ${role.description ?? ""}`.toLowerCase();
      const matchesQuery = !needle || haystack.includes(needle);
      const matchesStatus =
        statusFilter === "all" ||
        (statusFilter === "active" && role.is_active) ||
        (statusFilter === "inactive" && !role.is_active);
      const matchesOffering =
        !showClientOfferingFilter || offeringFilterValue === "all" || offeringLabelForRole(role) === offeringFilterValue;
      return matchesQuery && matchesStatus && matchesOffering;
    });
  }, [moduleRoles, offeringFilterValue, offeringLabelForRole, roleQuery, showClientOfferingFilter, statusFilter]);

  const totalRoleRows = roleRows.length;
  const totalRolePages = Math.max(1, Math.ceil(totalRoleRows / rolePageSize));
  const currentRolePage = Math.min(rolePage, totalRolePages);
  const roleRowStart = totalRoleRows === 0 ? 0 : (currentRolePage - 1) * rolePageSize + 1;
  const roleRowEnd = Math.min(currentRolePage * rolePageSize, totalRoleRows);
  const paginatedRoleRows = useMemo(
    () => roleRows.slice((currentRolePage - 1) * rolePageSize, currentRolePage * rolePageSize),
    [currentRolePage, rolePageSize, roleRows],
  );

  useEffect(() => {
    setRolePage(1);
    closeMenu();
  }, [closeMenu, roleQuery, statusFilter, offeringFilterValue, rolePageSize, roleKind, offeringId]);

  useEffect(() => {
    setOfferingFilterValue("all");
  }, [roleKind]);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      let catalog: OfferingCatalogItem[] = [];
      if (realm === "platform") {
        catalog = await offeringsApi.list();
        setOfferings(catalog);
      }
      if (realm === "platform" && roleKind === "all") {
        const [platformRoles, coreTemplates, ...offeringTemplateLists] = await Promise.all([
          listPlatformRoles(),
          defaultRolesApi.list({ offeringId: null, coreOnly: true }),
          ...catalog.map((offering) => defaultRolesApi.list({ offeringId: offering.offering_id, coreOnly: false })),
        ]);
        const merged: RoleRow[] = [
          ...platformRoles.map((role) => ({ ...role, _kind: "platform" as const })),
          ...[...coreTemplates, ...offeringTemplateLists.flat()].map((item) => ({
            ...toListedRole(item),
            _kind: "tenant" as const,
          })),
        ];
        setRoles(merged);
        setSelectedRoleId((current) => (merged.some((item) => item.role_id === current) ? current : merged[0]?.role_id || ""));
        return;
      }
      if (realm === "platform" && roleKind === "tenant") {
        const selectedOfferingItem = catalog.find((o) => o.offering_id === offeringId || o.code === offeringId);
        let templates: DefaultRoleListItem[] = [];
        if (offeringId === "all") {
          const [coreTemplates, ...offeringLists] = await Promise.all([
            defaultRolesApi.list({ offeringId: null, coreOnly: true }),
            ...catalog.map((offering) => defaultRolesApi.list({ offeringId: offering.offering_id, coreOnly: false })),
          ]);
          templates = [...coreTemplates, ...offeringLists.flat()];
        } else if (selectedOfferingItem) {
          templates = await defaultRolesApi.list({
            offeringId: selectedOfferingItem.offering_id,
            coreOnly: false,
          });
        } else {
          templates = await defaultRolesApi.list({
            offeringId: null,
            coreOnly: true,
          });
        }
        setRoles(templates.map((item) => ({ ...toListedRole(item), _kind: "tenant" as const })));
        setSelectedRoleId((current) =>
          templates.some((item) => item.role_id === current) ? current : templates[0]?.role_id || "",
        );
        return;
      }
      const rolesResult = await (realm === "platform" ? listPlatformRoles() : listTenantRoles());
      setRoles(rolesResult.map((role) => ({ ...role, _kind: realm === "platform" ? ("platform" as const) : undefined })));
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
    const foundRole = roles.find((role) => role.role_id === selectedRoleId);
    if (!foundRole && roles.length > 0) {
      return;
    }
    const isTemplate = realm === "platform" && (foundRole ? foundRole._kind === "tenant" : viewingKind === "tenant");
    const loadAccess = async () => {
      try {
        if (isTemplate) {
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
  }, [realm, roles, selectedRoleId, viewingKind]);

  useEffect(() => {
    if (moduleRoles.some((role) => role.role_id === selectedRoleId)) return;
    setSelectedRoleId(moduleRoles[0]?.role_id || "");
  }, [moduleRoles, selectedRoleId]);

  const tenantModuleOptions = useMemo(() => {
    const source = realm === "tenant" ? licensedOfferings : offerings;
    const platformOfferings = new Set([
      "PLATFORM_ADMINISTRATION",
      "PLATFORM_USER_ACCESS_MANAGEMENT",
      "TENANT_ADMINISTRATION",
      "USER_ACCESS_MANAGEMENT",
    ]);
    return [
      { value: "user_access_management", label: "User Access Management" },
      { value: "tenant_administration", label: "Tenant Administration" },
      ...source
        .filter((offering) => !platformOfferings.has(offering.code))
        .map((offering) => ({ value: offering.code, label: offering.display_name })),
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
        const key = entry.page.module || entry.page.offering_code || "General";
        return key === moduleKey ? { ...entry, access_level: accessLevel } : entry;
      }),
    );
  };

  const selectRoleKind = (nextKind: "all" | "platform" | "tenant") => {
    if (realm === "tenant") return;
    const next = new URLSearchParams(searchParams);
    if (nextKind === "all") {
      next.delete("type");
    } else {
      next.set("type", nextKind);
    }
    next.delete("offering_id");
    next.delete("scope");
    setSelectedRoleId("");
    setSearchParams(next, { replace: true });
  };

  const selectOfferingModule = (id: string) => {
    const next = new URLSearchParams(searchParams);
    if (realm === "platform") next.set("type", "tenant");
    if (id === "core" || id === "all") next.delete("offering_id");
    else next.set("offering_id", id);
    setSelectedRoleId("");
    setQuery("");
    setSearchParams(next, { replace: true });
  };

  // NEW: open a role from the table's "View" button — jumps into the permission studio.
  const openRole = (roleId: string) => {
    closeMenu();
    const found = roles.find((role) => role.role_id === roleId);
    setViewingKind(found?._kind ?? (roleKind === "tenant" ? "tenant" : "platform"));
    setSelectedRoleId(roleId);
    setError(null);
    setNotice(null);
    setQuery("");
    setView("detail");
  };

  // NEW: return to the roles table from the permission studio.
  const backToList = () => {
    setError(null);
    setView("list");
  };

  const openCreate = () => {
    if (!canModify) return;
    setCreateOpen(true);
    setError(null);
    const defaultKind: "platform" | "tenant" = realm === "tenant" ? "tenant" : roleKind === "tenant" ? "tenant" : "platform";
    setRoleForm({
      ...emptyRoleForm,
      role_type: defaultKind,
      module_scope: defaultKind === "tenant" ? (selectedOffering?.code ?? "user_access_management") : "platform_administration",
    });
  };

  // NEW: open "Edit details" for a role directly from its row menu in the table,
  // without navigating into the permission studio.
  const openEditFromRow = (role: RoleRow) => {
    closeMenu();
    if (!canModify) return;
    const kind: "platform" | "tenant" = role._kind ?? (roleKind === "tenant" ? "tenant" : "platform");
    setViewingKind(kind);
    setSelectedRoleId(role.role_id);
    setRoleForm({
      role_name: role.role_name,
      role_code: role.role_code,
      description: role.description ?? "",
      module_scope: role.module_scope ?? "",
      role_type: kind,
    });
    setEditOpen(true);
    setError(null);
  };

  const handleCreateRole = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!canModify) {
      setError("Modify permission required to create roles.");
      return;
    }
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
          module_scope: selectedCreateOffering ? selectedCreateOffering.code : roleForm.module_scope,
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
      setViewingKind(createAsTenant ? "tenant" : "platform");
      setSelectedRoleId(role.role_id);
      await load();
      setSelectedRoleId(role.role_id);
      // NEW: drop straight into the permission studio for the role just created.
      setView("detail");
    } catch (caught) {
      setError(errorMessage(caught));
    } finally {
      setSaving(false);
    }
  };

  const handleEditRole = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!selectedRoleId) return;
    if (!canModify) {
      setError("Modify permission required to update roles.");
      return;
    }
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
    if (!canModify) {
      setError("Modify permission required to save page permissions.");
      return;
    }
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
      {view === "list" ? (
        <>
          <header className={styles.rolesHeader}>
            <div>
              <p>Access control</p>
              <h1>Roles</h1>
              <span className={styles.lede}>
                {realm === "tenant"
                  ? "Manage roles and their access permissions."
                  : roleKind === "tenant"
                    ? "Default tenant roles that are copied when a workspace is registered."
                    : "Manage platform console roles and their access permissions."}
              </span>
            </div>
            {canModify && (
              <div className={styles.studioPageActions}>
                <Button type="button" onClick={openCreate}>
                  <Plus size={16} aria-hidden="true" />
                  Create Role
                </Button>
              </div>
            )}
          </header>

          {error && !createOpen && !editOpen && <Alert tone="error">{error}</Alert>}
          {notice && <Alert tone="success">{notice}</Alert>}

          <div className={styles.toolbar}>
            <div className={styles.searchField}>
              <Search size={16} aria-hidden="true" className={styles.searchIcon} />
              <input
                id={`${realm}-role-search`}
                type="text"
                placeholder="Search by role name"
                value={roleQuery}
                onChange={(event) => setRoleQuery(event.target.value)}
                aria-label="Search by role name"
              />
            </div>
            {realm === "platform" && (
              <label className={styles.filterField}>
                <span className={styles.srOnly}>Role type</span>
                <select
                  aria-label="Role type"
                  value={roleKind}
                  onChange={(event) => selectRoleKind(event.target.value as "all" | "platform" | "tenant")}
                >
                  <option value="all">All Role Types</option>
                  <option value="platform">Platform</option>
                  <option value="tenant">Tenant</option>
                </select>
              </label>
            )}
            {showClientOfferingFilter && (
              <label className={styles.filterField}>
                <span className={styles.srOnly}>Offering</span>
                <select
                  aria-label="Offering"
                  value={offeringFilterValue}
                  onChange={(event) => setOfferingFilterValue(event.target.value)}
                >
                  <option value="all">All Offerings</option>
                  <option value="Platform Administration">Platform Administration</option>
                  <option value="User Access Management">User Access Management</option>
                  {availableOfferingLabels
                    .filter((l) => l !== "Platform Administration" && l !== "User Access Management")
                    .map((label) => (
                      <option key={label} value={label}>
                        {label}
                      </option>
                    ))}
                </select>
              </label>
            )}
            {showOfferingFilter && (
              <label className={styles.filterField}>
                <span className={styles.srOnly}>Offering</span>
                <select
                  aria-label="Offering"
                  value={offeringId || "all"}
                  onChange={(event) => selectOfferingModule(event.target.value)}
                >
                  <option value="all">All Offerings</option>
                  <option value="user_access_management">User Access Management</option>
                  <option value="tenant_administration">Tenant Administration</option>
                  {(realm === "tenant" ? licensedOfferings : offerings)
                    .filter(
                      (offering) =>
                        offering.code !== "PLATFORM_ADMINISTRATION" &&
                        offering.code !== "PLATFORM_USER_ACCESS_MANAGEMENT" &&
                        offering.code !== "TENANT_ADMINISTRATION" &&
                        offering.code !== "USER_ACCESS_MANAGEMENT",
                    )
                    .map((offering) => (
                      <option key={offering.offering_id} value={offering.code}>
                        {offering.display_name}
                      </option>
                    ))}
                </select>
              </label>
            )}
            <label className={styles.filterField}>
              <span className={styles.srOnly}>Status</span>
              <select
                aria-label="Status"
                value={statusFilter}
                onChange={(event) => setStatusFilter(event.target.value as typeof statusFilter)}
              >
                <option value="all">All statuses</option>
                <option value="active">Active</option>
                <option value="inactive">Inactive</option>
              </select>
            </label>
          </div>

          <div className={styles.panel}>
            {loading ? (
              <div className={styles.loading}>Loading roles…</div>
            ) : (
              <div className={styles.tableWrap}>
                <table>
                  <thead>
                    <tr>
                      <th>Role name</th>
                      <th>Role type</th>
                      <th>Offering</th>
                      <th>Description</th>
                      <th>Status</th>
                      <th>Created</th>
                      <th className={styles.actionsHeader}>Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {paginatedRoleRows.map((role) => (
                      <tr key={role.role_id}>
                        <td>
                          <div className={styles.identityText}>
                            <span className={styles.identityName}>{role.role_name}</span>
                            <span className={styles.identityMeta}>{role.role_code}</span>
                          </div>
                        </td>
                        <td>
                          {(() => {
                            const isTenantKind = role._kind ? role._kind === "tenant" : realm === "tenant" || roleKind === "tenant";
                            return (
                              <span className={isTenantKind ? styles.roleChipTenant : styles.roleChipPlatform}>
                                {isTenantKind ? "Tenant" : "Platform"}
                              </span>
                            );
                          })()}
                        </td>
                        <td>{offeringLabelForRole(role)}</td>
                        <td>{role.description || "—"}</td>
                        <td>
                          <span className={`${styles.status} ${role.is_active ? styles.statusActive : styles.statusInactive}`}>
                            <i className={`${styles.dot} ${!role.is_active ? styles.dotInactive : ""}`} aria-hidden="true" />
                            {role.is_active ? "ACTIVE" : "INACTIVE"}
                          </span>
                        </td>
                        <td>{formatCreatedDate(role.created_at)}</td>
                        <td className={styles.actionsCell}>
                          <div className={styles.rowActions}>
                            <button
                              type="button"
                              className={styles.tableActionButton}
                              onClick={() => openRole(role.role_id)}
                            >
                              {canModify ? <Pencil size={13} aria-hidden="true" /> : <Eye size={13} aria-hidden="true" />}
                              <span>{canModify ? "View / Edit" : "View"}</span>
                            </button>
                            {canModify && (
                              <button
                                type="button"
                                className={styles.iconButton}
                                aria-label={`More actions for ${role.role_name}`}
                                aria-haspopup="menu"
                                aria-expanded={menuId === role.role_id}
                                onClick={(event) => toggleMenu(role.role_id, event.currentTarget)}
                              >
                                <MoreHorizontal size={18} aria-hidden="true" />
                              </button>
                            )}
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                {roleRows.length === 0 && (
                  <div className={styles.empty}>
                    {roleQuery || statusFilter !== "all" ? "No roles match this search." : "No roles yet. Create one to set page access."}
                  </div>
                )}
                {roleRows.length > 0 && (
                  <nav className={styles.pagination} aria-label="Roles table pagination">
                    <span className={styles.paginationSummary}>
                      Showing {roleRowStart}–{roleRowEnd} of {totalRoleRows} roles
                    </span>
                    <label className={styles.pageSizeControl}>
                      Rows per page
                      <select
                        value={rolePageSize}
                        onChange={(event) => setRolePageSize(Number(event.target.value))}
                        aria-label="Rows per page"
                      >
                        {PAGE_SIZE_OPTIONS.map((size) => (
                          <option key={size} value={size}>
                            {size}
                          </option>
                        ))}
                      </select>
                    </label>
                    <div className={styles.paginationActions}>
                      <Button
                        type="button"
                        variant="secondary"
                        disabled={currentRolePage <= 1}
                        onClick={() => setRolePage((value) => Math.max(1, value - 1))}
                        aria-label="Previous page"
                      >
                        <ChevronLeft size={15} aria-hidden="true" />
                        Previous
                      </Button>
                      <span className={styles.pageIndicator}>
                        Page {currentRolePage} of {totalRolePages}
                      </span>
                      <Button
                        type="button"
                        variant="secondary"
                        disabled={currentRolePage >= totalRolePages}
                        onClick={() => setRolePage((value) => Math.min(totalRolePages, value + 1))}
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
        </>
      ) : (
        <>
          <div className={styles.studioPageActions} style={{ marginBottom: "0.75rem" }}>
            <button type="button" className={styles.simpleBackButton} onClick={backToList}>
              <ArrowLeft size={18} aria-hidden="true" />
              <span>Back to roles</span>
            </button>
          </div>

          {error && !createOpen && !editOpen && <Alert tone="error">{error}</Alert>}
          {notice && <Alert tone="success">{notice}</Alert>}

          {loading ? (
            <div className={styles.loading}>Loading role…</div>
          ) : !selectedRole ? (
            <div className={styles.rolesEmpty}>
              <Shield size={28} aria-hidden="true" />
              <h2>Role not found</h2>
              <p>It may have been removed. Go back to the roles list to pick another.</p>
              <button type="button" className={styles.simpleBackButton} onClick={backToList}>
                <ArrowLeft size={18} aria-hidden="true" />
                <span>Back to roles</span>
              </button>
            </div>
          ) : (
            <article className={styles.studio}>
              <div className={styles.studioHeader}>
                <div>
                  <h2>{selectedRole.role_name}</h2>
                  <p>Code: {selectedRole.role_code}</p>
                </div>
                <div className={styles.studioActions}>
                  {canModify && (
                    <Button
                      type="button"
                      variant="secondary"
                      onClick={() => {
                        setRoleForm({
                          role_name: selectedRole.role_name,
                          role_code: selectedRole.role_code,
                          description: selectedRole.description ?? "",
                          module_scope: selectedRole.module_scope ?? "",
                          role_type: effectiveDetailKind,
                        });
                        setEditOpen(true);
                        setError(null);
                      }}
                    >
                      <Pencil size={15} aria-hidden="true" />
                      Edit details
                    </Button>
                  )}
                  <Button type="button" onClick={() => void handleSave()} loading={saving} disabled={unsavedCount === 0 || !canModify}>
                    Save changes
                  </Button>
                </div>
              </div>

              {!canModify && (
                <Alert tone="info" title="Read-only mode">
                  You have view-only access to roles and permissions. Modifying permissions is disabled.
                </Alert>
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
                  <small>Offering</small>
                  <strong>{offeringLabelForRole(selectedRole)}</strong>
                </article>
              </div>

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
                      <span>
                        {entries.length} {entries.length === 1 ? "page" : "pages"}
                      </span>
                    </div>
                    {canModify && (
                      <div className={styles.bulk}>
                        <button type="button" onClick={() => setModuleAccess(module, "none")}>
                          None
                        </button>
                        <button type="button" className={styles.bulkView} onClick={() => setModuleAccess(module, "view")}>
                          View all
                        </button>
                        <button type="button" className={styles.bulkModify} onClick={() => setModuleAccess(module, "modify")}>
                          Modify all
                        </button>
                      </div>
                    )}
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
                            disabled={!canModify}
                            className={
                              entry.access_level === level
                                ? `${styles.segmentActive} ${level === "none" ? styles.segmentNone : ""} ${level === "view" ? styles.segmentView : ""}`
                                : ""
                            }
                            onClick={() => {
                              if (!canModify) return;
                              setPageAccess((current) =>
                                current.map((item) =>
                                  item.page.page_id === entry.page.page_id ? { ...item, access_level: level } : item,
                                ),
                              );
                            }}
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
                  {sensitiveOnly || query ? "No pages match this search." : "No pages are available for this role yet."}
                </div>
              )}
            </article>
          )}
        </>
      )}

      {createOpen && (
        <div className={styles.backdrop}>
          <form className={styles.dialog} role="dialog" aria-labelledby={`${realm}-new-role-title`} onSubmit={handleCreateRole}>
            <div className={styles.dialogHeader}>
              <div>
                <h2 id={`${realm}-new-role-title`}>New role</h2>
                <p>
                  {realm === "tenant"
                    ? "Choose an offering. Permissions will include only that offering’s pages."
                    : "Platform roles use the console. Tenant roles apply to an offering or licensed module."}
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
                        onChange={() => setRoleForm((current) => ({ ...current, role_type: "platform", module_scope: "platform_administration" }))}
                      />
                      Platform
                    </label>
                    <label>
                      <input
                        type="radio"
                        name="new-role-type"
                        checked={roleForm.role_type === "tenant"}
                        onChange={() => setRoleForm((current) => ({ ...current, role_type: "tenant", module_scope: "user_access_management" }))}
                      />
                      Tenant
                    </label>
                  </div>
                </fieldset>
              )}
              {roleForm.role_type === "platform" ? (
                <label className={styles.span2}>
                  <strong>Offering</strong>
                  <select
                    aria-label="Offering"
                    value={roleForm.module_scope}
                    onChange={(event) => setRoleForm((current) => ({ ...current, module_scope: event.target.value }))}
                  >
                    <option value="platform_administration">Platform Administration</option>
                    <option value="user_access_management">User Access Management</option>
                  </select>
                </label>
              ) : (
                <label className={styles.span2}>
                  <strong>Offering</strong>
                  <select
                    required
                    aria-label="Offering"
                    value={roleForm.module_scope}
                    onChange={(event) => setRoleForm((current) => ({ ...current, module_scope: event.target.value }))}
                  >
                    {tenantModuleOptions.map((option) => (
                      <option key={option.value} value={option.value}>
                        {option.label}
                      </option>
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
              <Button type="button" variant="secondary" onClick={() => setCreateOpen(false)}>
                Cancel
              </Button>
              <Button type="submit" loading={saving} loadingLabel="Creating…">
                Create role
              </Button>
            </div>
          </form>
        </div>
      )}

      {editOpen && (
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
              <Button type="button" variant="secondary" onClick={() => setEditOpen(false)}>
                Cancel
              </Button>
              <Button type="submit" loading={saving} loadingLabel="Saving…">
                Save role
              </Button>
            </div>
          </form>
        </div>
      )}

      {/* NEW: portal-rendered row actions menu for the roles table ("..." button). */}
      {menuId &&
        menuPosition &&
        typeof document !== "undefined" &&
        createPortal(
          (() => {
            const activeRole = roleRows.find((role) => role.role_id === menuId);
            if (!activeRole) return null;
            return (
              <div
                ref={menuPanelRef}
                className={styles.menuPortal}
                role="menu"
                style={{ top: menuPosition.top, left: menuPosition.left }}
              >
                <button type="button" role="menuitem" onClick={() => openEditFromRow(activeRole)}>
                  <Pencil size={14} aria-hidden="true" />
                  Edit details
                </button>
              </div>
            );
          })(),
          document.body,
        )}
    </section>
  );
};
