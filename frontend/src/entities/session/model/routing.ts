import { useParams } from "react-router-dom";

import { useSession } from "./session-context";
import type { SessionPrincipal } from "./session";

export const normalizeTenantCode = (code: string): string => code.trim().toUpperCase();

export const tenantLoginPath = (tenantCode: string): string =>
  `/t/${normalizeTenantCode(tenantCode)}/login`;

export const tenantAppPath = (tenantCode: string, appPath = "/app/overview"): string => {
  const code = normalizeTenantCode(tenantCode);
  const path = appPath.startsWith("/app")
    ? appPath
    : `/app${appPath.startsWith("/") ? appPath : `/${appPath}`}`;
  return `/t/${code}${path}`;
};

export const useTenantAppPath = () => {
  const params = useParams<{ tenantCode?: string }>();
  const { principal } = useSession();
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

  return tenantAppPath(principal.tenant.tenant_code, "/app/overview");
};

export const getTenantLoginPath = (principal: SessionPrincipal | null): string => {
  if (principal?.principal_type === "tenant_user") {
    return tenantLoginPath(principal.tenant.tenant_code);
  }
  return "/login";
};
