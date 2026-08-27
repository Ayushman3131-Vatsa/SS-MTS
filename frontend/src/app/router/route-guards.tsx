import type { PropsWithChildren } from "react";
import { Navigate, Outlet, useLocation, useParams } from "react-router-dom";

import {
  getPrincipalHome,
  normalizeTenantCode,
  tenantAppPath,
  tenantLoginPath,
} from "../../entities/session/model/routing";
import { canAccessPage } from "../../entities/session/model/page-access";
import { useSession } from "../../entities/session/model/session-context";
import type { AccessLevel, TenantRole } from "../../entities/session/model/session";
import { FullPageLoader } from "../../shared/ui/FullPageLoader/FullPageLoader";

export const PublicOnlyRoute = () => {
  const { principal, status } = useSession();
  const { tenantCode } = useParams<{ tenantCode?: string }>();

  if (status === "bootstrapping") {
    return <FullPageLoader />;
  }

  if (principal) {
    return <Navigate to={getPrincipalHome(principal)} replace />;
  }

  if (tenantCode && tenantCode !== normalizeTenantCode(tenantCode)) {
    return <Navigate to={tenantLoginPath(tenantCode)} replace />;
  }

  return <Outlet />;
};

interface ProtectedRouteProps {
  area?: "platform" | "tenant";
  roles?: TenantRole[];
  allowSuspendedTenant?: boolean;
  allowPasswordChangeRequired?: boolean;
}

interface OfferingRouteProps {
  code: string;
}

interface PageAccessRouteProps {
  route: string;
  minimum?: AccessLevel;
}

export const PageAccessRoute = ({ route, minimum = "view" }: PageAccessRouteProps) => {
  const { principal, status } = useSession();
  const { tenantCode } = useParams<{ tenantCode?: string }>();

  if (status === "bootstrapping") return <FullPageLoader />;
  if (!principal) {
    return <Navigate to={tenantCode ? tenantLoginPath(tenantCode) : "/login"} replace />;
  }
  if (!canAccessPage(principal, route, minimum)) {
    return <Navigate to={getPrincipalHome(principal)} replace />;
  }

  return <Outlet />;
};

export const OfferingRoute = ({ code }: OfferingRouteProps) => {
  const { principal, status } = useSession();
  const { tenantCode } = useParams<{ tenantCode?: string }>();

  if (status === "bootstrapping") return <FullPageLoader />;
  if (!principal) {
    return <Navigate to={tenantCode ? tenantLoginPath(tenantCode) : "/login"} replace />;
  }
  if (principal.principal_type !== "tenant_user") return <Navigate to="/forbidden" replace />;

  const isEffective = principal.tenant.offerings.some((offering) => offering.code === code);
  return isEffective ? <Outlet /> : <Navigate to={getPrincipalHome(principal)} replace />;
};

export const TenantWorkspaceGuard = () => {
  const { principal, status } = useSession();
  const { tenantCode } = useParams<{ tenantCode?: string }>();

  if (status === "bootstrapping") {
    return <FullPageLoader />;
  }
  if (!principal || principal.principal_type !== "tenant_user" || !tenantCode) {
    return <Navigate to={tenantCode ? tenantLoginPath(tenantCode) : "/login"} replace />;
  }
  if (normalizeTenantCode(tenantCode) !== principal.tenant.tenant_code) {
    return <Navigate to={getPrincipalHome(principal)} replace />;
  }
  return <Outlet />;
};

export const LegacyTenantAppRedirect = () => {
  const location = useLocation();
  const { principal, status } = useSession();

  if (status === "bootstrapping") {
    return <FullPageLoader />;
  }
  if (principal?.principal_type === "tenant_user") {
    return (
      <Navigate
        to={`/t/${principal.tenant.tenant_code}${location.pathname}${location.search}`}
        replace
      />
    );
  }
  return <Navigate to="/login" replace />;
};

export const TenantPathNavigate = ({ to }: { to: string }) => {
  const { tenantCode } = useParams<{ tenantCode?: string }>();
  if (!tenantCode) {
    return <Navigate to="/login" replace />;
  }
  return <Navigate to={tenantAppPath(tenantCode, to)} replace />;
};

export const ProtectedRoute = ({
  area,
  allowSuspendedTenant = false,
  allowPasswordChangeRequired = false,
  roles,
}: ProtectedRouteProps) => {
  const { principal, status } = useSession();
  const { tenantCode } = useParams<{ tenantCode?: string }>();

  if (status === "bootstrapping") {
    return <FullPageLoader />;
  }

  if (!principal) {
    return <Navigate to={tenantCode ? tenantLoginPath(tenantCode) : "/login"} replace />;
  }

  if (principal.password_change_required && !allowPasswordChangeRequired) {
    return <Navigate to="/account/change-password" replace />;
  }

  if (area === "platform" && principal.principal_type !== "platform_admin") {
    return <Navigate to="/forbidden" replace />;
  }

  if (area === "tenant" && principal.principal_type !== "tenant_user") {
    return <Navigate to="/forbidden" replace />;
  }

  if (
    area === "tenant" &&
    principal.principal_type === "tenant_user" &&
    principal.tenant.status === "SUSPENDED" &&
    !allowSuspendedTenant
  ) {
    return <Navigate to={tenantAppPath(principal.tenant.tenant_code, "/app/suspended")} replace />;
  }

  if (
    roles &&
    (principal.principal_type !== "tenant_user" ||
      !roles.includes(principal.role))
  ) {
    return <Navigate to="/forbidden" replace />;
  }

  return <Outlet />;
};

export const SessionReady = ({ children }: PropsWithChildren) => {
  const { status } = useSession();
  return status === "bootstrapping" ? <FullPageLoader /> : children;
};
