/** Internal placeholder domain when no work email is provided at account creation. */
export const SYNTHETIC_ACCOUNT_EMAIL_DOMAIN = "accounts.local";

export function isSyntheticAccountEmail(email: string | null | undefined): boolean {
  if (!email) {
    return false;
  }
  return email.trim().toLowerCase().endsWith(`@${SYNTHETIC_ACCOUNT_EMAIL_DOMAIN}`);
}

/** Show a real work email in UI; hide internal storage placeholders. */
export function formatAccountEmailForDisplay(email: string | null | undefined): string | null {
  if (!email || isSyntheticAccountEmail(email)) {
    return null;
  }
  return email;
}
