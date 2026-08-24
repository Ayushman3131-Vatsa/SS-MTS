import type { SessionPrincipal } from "./session";

export const getPrincipalHome = (principal: SessionPrincipal): string => {
  if (principal.password_change_required) {
    return "/account/change-password";
  }

  if (principal.principal_type === "platform_admin") {
    return "/platform";
  }

  if (principal.tenant.status === "SUSPENDED") {
    return "/app/suspended";
  }

  return "/app/overview";
};