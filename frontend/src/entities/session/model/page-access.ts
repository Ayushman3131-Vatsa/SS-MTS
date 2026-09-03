import type { AccessLevel, SessionPrincipal } from "./session";

const rank: Record<AccessLevel, number> = {
  none: 0,
  view: 1,
  modify: 2,
};

const matchingGrant = (principal: SessionPrincipal | null | undefined, route: string) => {
  if (!principal?.page_access || principal.page_access.length === 0) {
    return undefined;
  }
  // 1. Direct exact match has highest priority
  const exact = principal.page_access.find((entry) => entry.route === route);
  if (exact) {
    return exact;
  }
  // 2. Specific prefix match for nested routes (excluding root shell routes like '/platform' and '/app')
  const prefixes = principal.page_access
    .filter(
      (entry) =>
        entry.route !== "/platform" &&
        entry.route !== "/app" &&
        (route.startsWith(`${entry.route}/`) || route.startsWith(`${entry.route}?`)),
    )
    .sort((a, b) => b.route.length - a.route.length);

  return prefixes[0];
};

export const pageAccessLevel = (
  principal: SessionPrincipal | null | undefined,
  route: string,
): AccessLevel => matchingGrant(principal, route)?.access_level ?? "none";

export const canAccessPage = (
  principal: SessionPrincipal | null | undefined,
  route: string,
  minimum: AccessLevel = "view",
): boolean => {
  if (!principal) {
    return true;
  }
  const grants = principal?.page_access;
  if (!grants || grants.length === 0) {
    if (principal?.principal_type === "platform_admin") {
      return principal.role === "Platform Admin";
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
  const hasRoles = Boolean(
    (principal.roles && principal.roles.length > 0 && principal.roles.some((r) => r !== "Unassigned")) ||
    (principal.role && principal.role !== "Unassigned")
  );
  if (!hasRoles) {
    return false;
  }
  return principal.tenant.offerings.some((offering) => offering.code === offeringCode);
};

export const canModifyPage = (
  principal: SessionPrincipal | null | undefined,
  route: string,
): boolean => canAccessPage(principal, route, "modify");
