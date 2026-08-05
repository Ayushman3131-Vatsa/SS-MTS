export const SESSION_EXPIRED_EVENT = "workspace:session-expired";
export const TENANT_ACCESS_CHANGED_EVENT = "workspace:tenant-access-changed";

export const announceSessionExpiry = (): void => {
  window.dispatchEvent(new Event(SESSION_EXPIRED_EVENT));
};

export const announceTenantAccessChanged = (code: string): void => {
  window.dispatchEvent(new CustomEvent(TENANT_ACCESS_CHANGED_EVENT, { detail: { code } }));
};
