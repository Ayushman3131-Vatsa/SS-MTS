import { apiRequest } from "../../../shared/api/client";

export type AccessLevel = "none" | "view" | "modify";

export interface Role {
  role_id: string;
  role_code: string;
  role_name: string;
  description: string | null;
  is_system: boolean;
  is_active: boolean;
  module_scope?: string | null;
  users_count: number;
  created_at: string;
}

export interface PlatformUser {
  admin_id: string;
  name: string;
  username: string;
  email: string;
  employee_id?: string | null;
  roles: Role[];
  is_active?: boolean;
  failed_login_count: number;
  locked_until: string | null;
  last_login_at: string | null;
  created_at: string;
  temporary_password?: string | null;
}

export interface TenantUser {
  tenant_id: string;
  user_id: string;
  name: string;
  username: string;
  email: string;
  employee_id: string | null;
  role: string;
  roles: string[];
  status: "Active" | "Inactive";
  version: number;
  created_by_user_id: string | null;
  last_login_at: string | null;
  created_at: string;
  temporary_password?: string | null;
}

export interface Page {
  page_id: string;
  page_code: string;
  module: string;
  page_name: string;
  route: string;
  app_scope: string;
  offering_code?: string | null;
}

export interface PageAccess {
  page: Page;
  access_level: AccessLevel;
}

export const listPlatformUsers = () =>
  apiRequest<PlatformUser[]>("/platform/users");

export const listPlatformPages = () => apiRequest<Page[]>("/platform/pages");

export const createPlatformUser = (payload: {
  name?: string;
  email?: string;
  username: string;
  employee_id?: string;
  role_ids: string[];
}) =>
  apiRequest<PlatformUser>("/platform/users", {
    method: "POST",
    body: payload,
  });

export const updatePlatformUser = (
  adminId: string,
  payload: { name?: string; username?: string; employee_id?: string | null; is_active?: boolean },
) =>
  apiRequest<PlatformUser>(`/platform/users/${adminId}`, {
    method: "PATCH",
    body: payload,
  });

export const assignPlatformUserRoles = (adminId: string, roleIds: string[]) =>
  apiRequest<PlatformUser>(`/platform/users/${adminId}/roles`, {
    method: "PUT",
    body: { role_ids: roleIds },
  });

export const listPlatformRoles = () => apiRequest<Role[]>("/platform/roles");

export const createPlatformRole = (payload: {
  role_name: string;
  role_code?: string;
  description?: string;
  module_scope?: string;
}) =>
  apiRequest<Role>("/platform/roles", {
    method: "POST",
    body: payload,
  });

export const updatePlatformRole = (
  roleId: string,
  payload: { role_name?: string; description?: string | null },
) =>
  apiRequest<Role>(`/platform/roles/${roleId}`, {
    method: "PATCH",
    body: payload,
  });

export const deletePlatformRole = (roleId: string) =>
  apiRequest<void>(`/platform/roles/${roleId}`, { method: "DELETE" });

export const listPlatformPageAccess = (roleId: string) =>
  apiRequest<PageAccess[]>(`/platform/roles/${roleId}/page-access`);

export const savePlatformPageAccess = (
  roleId: string,
  entries: { page_id: string; access_level: AccessLevel }[],
) =>
  apiRequest<PageAccess[]>(`/platform/roles/${roleId}/page-access`, {
    method: "PUT",
    body: { entries },
  });

export const listTenantUsers = () => apiRequest<TenantUser[]>("/users");

export const listTenantPages = () => apiRequest<Page[]>("/pages");

export const createTenantUser = (payload: {
  name?: string;
  employee_id?: string;
  username: string;
  email?: string;
  role_ids: string[];
}) =>
  apiRequest<TenantUser>("/users", {
    method: "POST",
    body: payload,
  });

export const updateTenantUser = (
  userId: string,
  payload: {
    name?: string;
    username?: string;
    employee_id?: string | null;
    status?: "Active" | "Inactive";
    version: number;
  },
) =>
  apiRequest<TenantUser>(`/users/${userId}`, {
    method: "PATCH",
    body: payload,
  });

export const assignTenantUserRoles = (userId: string, roleIds: string[]) =>
  apiRequest<void>(`/users/${userId}/roles`, {
    method: "PUT",
    body: { role_ids: roleIds },
  });

export const listTenantRoles = () => apiRequest<Role[]>("/roles");

export const createTenantRole = (payload: {
  role_name: string;
  role_code?: string;
  description?: string;
  module_scope?: string;
}) =>
  apiRequest<Role>("/roles", {
    method: "POST",
    body: payload,
  });

export const updateTenantRole = (
  roleId: string,
  payload: { role_name?: string; description?: string | null },
) =>
  apiRequest<Role>(`/roles/${roleId}`, {
    method: "PATCH",
    body: payload,
  });

export const deleteTenantRole = (roleId: string) =>
  apiRequest<void>(`/roles/${roleId}`, { method: "DELETE" });

export const listTenantPageAccess = (roleId: string) =>
  apiRequest<PageAccess[]>(`/roles/${roleId}/page-access`);

export const saveTenantPageAccess = (
  roleId: string,
  entries: { page_id: string; access_level: AccessLevel }[],
) =>
  apiRequest<PageAccess[]>(`/roles/${roleId}/page-access`, {
    method: "PUT",
    body: { entries },
  });
