import type { PropsWithChildren } from "react";
import { Navigate, Outlet } from "react-router-dom";

import { getPrincipalHome } from "../../entities/session/model/routing";
import { useSession } from "../../entities/session/model/session-context";
import type { TenantRole } from "../../entities/session/model/session";
import { FullPageLoader } from "../../shared/ui/FullPageLoader/FullPageLoader";

export const PublicOnlyRoute = () => {
  const { principal, status } = useSession();

  if (status === "bootstrapping") {
    return <FullPageLoader />;
  }

  if (principal) {
    return <Navigate to={getPrincipalHome(principal)} replace />;
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

export const OfferingRoute = ({ code }: OfferingRouteProps) => {
  const { principal, status } = useSession();

  if (status === "bootstrapping") return <FullPageLoader />;
  if (!principal) return <Navigate to="/login" replace />;
  if (principal.principal_type !== "tenant_user") return <Navigate to="/forbidden" replace />;

  const isEffective = principal.tenant.offerings.some((offering) => offering.code === code);
  return isEffective ? <Outlet /> : <Navigate to={getPrincipalHome(principal)} replace />;
};

export const ProtectedRoute = ({
  area,
  allowSuspendedTenant = false,
  allowPasswordChangeRequired = false,
  roles,
}: ProtectedRouteProps) => {
  const { principal, status } = useSession();

  if (status === "bootstrapping") {
    return <FullPageLoader />;
  }

  if (!principal) {
    return <Navigate to="/login" replace />;
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
    principal.password_change_required &&
    !allowPasswordChangeRequired
  ) {
    return <Navigate to="/account/change-password" replace />;
  }

  if (
    area === "tenant" &&
    principal.principal_type === "tenant_user" &&
    principal.tenant.status === "SUSPENDED" &&
    !allowSuspendedTenant
  ) {
    return <Navigate to="/app/suspended" replace />;
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
