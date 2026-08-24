export type AccessLevel = "none" | "view" | "modify";

export const TENANT_ROLES = [
  "Tenant Admin",
] as const;

export type TenantRole = (typeof TENANT_ROLES)[number] | (string & {});
export type PlatformRole = "Platform Admin" | (string & {});
export type SessionRole = PlatformRole | TenantRole;

export interface SessionTenant {
  tenant_id: string;
  org_name: string;
  tenant_code: string;
  status: "ACTIVE" | "SUSPENDED";
  offerings: SessionOffering[];
}

export interface SessionOffering {
  offering_id: string;
  code: string;
  display_name: string;
  description: string;
  icon_key: string;
  route_slug: string;
  sort_order: number;
}

export interface SessionPageAccess {
  page_code: string;
  module: string;
  page_name: string;
  route: string;
  access_level: AccessLevel;
  offering_code: string | null;
}

export interface PlatformPrincipal {
  principal_type: "platform_admin";
  principal_id: string;
  name: string;
  email: string;
  role: PlatformRole;
  roles?: string[];
  page_access?: SessionPageAccess[];
  tenant: null;
  password_change_required: boolean;
}

export interface TenantPrincipal {
  principal_type: "tenant_user";
  principal_id: string;
  name: string;
  email: string;
  role: TenantRole;
  roles?: string[];
  page_access?: SessionPageAccess[];
  tenant: SessionTenant;
  password_change_required: boolean;
}

export type SessionPrincipal = PlatformPrincipal | TenantPrincipal;

export interface TenantLoginCredentials {
  email: string;
  password: string;
}

export interface PasswordChangeCredentials {
  current_password: string;
  new_password: string;
}

export interface PlatformLoginCredentials {
  email: string;
  password: string;
}

export type SessionStatus =
  | "bootstrapping"
  | "authenticated"
  | "unauthenticated";
