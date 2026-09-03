import { useParams } from "react-router-dom";

import { useOptionalSession } from "./session-context";
import type { SessionPrincipal } from "./session";
import { canAccessPage } from "./page-access";

export const normalizeTenantCode = (code: string): string => code.trim().toUpperCase();

export const tenantLoginPath = (tenantCode: string): string =>
  `/${normalizeTenantCode(tenantCode)}/login`;

export const tenantAppPath = (tenantCode: string, appPath = "/app/overview"): string => {
  const code = normalizeTenantCode(tenantCode);
  const path = appPath.startsWith("/app")
    ? appPath
    : `/app${appPath.startsWith("/") ? appPath : `/${appPath}`}`;
  return `/${code}${path}`;
};

export const useTenantAppPath = () => {
  const params = useParams<{ tenantCode?: string }>();
  const principal = useOptionalSession()?.principal;
  const code =
    (params.tenantCode ? normalizeTenantCode(params.tenantCode) : "") ||
    (principal?.principal_type === "tenant_user" ? principal.tenant.tenant_code : "");
  return (appPath: string) => (code ? tenantAppPath(code, appPath) : appPath);
};

export const getPrincipalHome = (principal: SessionPrincipal): string => {
  if (principal.password_change_required) {
    return "/account/change-password";
  }

  if (principal.principal_type === "platform_admin") {
    return "/platform";
  }

  if (principal.tenant.status === "SUSPENDED") {
    return tenantAppPath(principal.tenant.tenant_code, "/app/suspended");
  }

  // 1. If user has access to Overview, that is their primary landing
  if (canAccessPage(principal, "/app/overview")) {
    return tenantAppPath(principal.tenant.tenant_code, "/app/overview");
  }

  // 2. Otherwise find the first page they can actually access
  const preferredRoutes = [
    "/app/task-management",
    "/app/my-work",
    "/app/users",
    "/app/roles",
    "/app/configurations",
  ];

  for (const preferred of preferredRoutes) {
    if (canAccessPage(principal, preferred)) {
      return tenantAppPath(principal.tenant.tenant_code, preferred);
    }
  }

  // Fallback to any route in page_access where access_level is not 'none'
  const accessibleGrant = principal.page_access?.find(
    (entry) => entry.access_level && entry.access_level !== "none" && entry.route?.startsWith("/app"),
  );
  if (accessibleGrant) {
    return tenantAppPath(principal.tenant.tenant_code, accessibleGrant.route);
  }

  // If user has no roles/pages assigned, land on default shell
  return tenantAppPath(principal.tenant.tenant_code, "/app/overview");
};

export const getTenantLoginPath = (principal: SessionPrincipal | null): string => {
  if (principal?.principal_type === "tenant_user") {
    return tenantLoginPath(principal.tenant.tenant_code);
  }
  return "/login";
};
