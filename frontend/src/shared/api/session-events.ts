export const SESSION_EXPIRED_EVENT = "workspace:session-expired";

export const announceSessionExpiry = (): void => {
  window.dispatchEvent(new Event(SESSION_EXPIRED_EVENT));
};
