import type { SessionPrincipal } from "./session";

export const getPrincipalHome = (principal: SessionPrincipal): string => {
  if (principal.principal_type === "platform_admin") {
    return "/platform";
  }

  return principal.role === "Employee" ? "/app/my-work" : "/app/overview";
};
