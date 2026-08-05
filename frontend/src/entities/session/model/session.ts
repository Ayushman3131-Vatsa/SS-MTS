export const TENANT_ROLES = [
  "Tenant Admin",
  "Project Manager",
  "Employee",
] as const;

export type TenantRole = (typeof TENANT_ROLES)[number];
export type PlatformRole = "Platform Admin";
export type SessionRole = PlatformRole | TenantRole;

export interface SessionTenant {
  tenant_id: string;
  org_name: string;
  workspace_slug: string;
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

export interface PlatformPrincipal {
  principal_type: "platform_admin";
  principal_id: string;
  name: string;
  email: string;
  role: PlatformRole;
  tenant: null;
}

export interface TenantPrincipal {
  principal_type: "tenant_user";
  principal_id: string;
  name: string;
  email: string;
  role: TenantRole;
  tenant: SessionTenant;
}

export type SessionPrincipal = PlatformPrincipal | TenantPrincipal;

export interface TenantLoginCredentials {
  workspace_slug: string;
  email: string;
  password: string;
}

export interface PlatformLoginCredentials {
  email: string;
  password: string;
}

export type SessionStatus =
  | "bootstrapping"
  | "authenticated"
  | "unauthenticated";
