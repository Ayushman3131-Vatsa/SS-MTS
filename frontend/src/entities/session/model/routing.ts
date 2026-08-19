import type { SessionPrincipal } from "./session";

export const getPrincipalHome = (principal: SessionPrincipal): string => {
  if (principal.principal_type === "platform_admin") {
    return "/platform";
  }

  if (principal.tenant.status === "SUSPENDED") {
    return "/app/suspended";
  }

  return principal.role === "Employee" ? "/app/my-work" : "/app/overview";
};
