import type { AccessLevel, SessionPrincipal } from "./session";

const rank: Record<AccessLevel, number> = {
  none: 0,
  view: 1,
  modify: 2,
};

const matchingGrant = (principal: SessionPrincipal | null | undefined, route: string) =>
  principal?.page_access?.find(
    (entry) => entry.route === route || route.startsWith(`${entry.route}/`),
  );

export const pageAccessLevel = (
  principal: SessionPrincipal | null | undefined,
  route: string,
): AccessLevel => matchingGrant(principal, route)?.access_level ?? "none";

export const canAccessPage = (
  principal: SessionPrincipal | null | undefined,
  route: string,
  minimum: AccessLevel = "view",
): boolean => {
  const grants = principal?.page_access;
  if (!grants || grants.length === 0) {
    if (principal?.principal_type === "platform_admin") {
      return true;
    }
    return principal?.principal_type === "tenant_user" && principal.role === "Tenant Admin";
  }
  return rank[pageAccessLevel(principal, route)] >= rank[minimum];
};

export const canAccessOffering = (
  principal: SessionPrincipal | null | undefined,
  offeringCode: string,
): boolean => {
  if (principal?.principal_type !== "tenant_user") {
    return false;
  }
  return principal.tenant.offerings.some((offering) => offering.code === offeringCode);
};
