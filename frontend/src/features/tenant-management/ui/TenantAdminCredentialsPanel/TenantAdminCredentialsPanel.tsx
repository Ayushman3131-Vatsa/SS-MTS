import { Check, Copy, KeyRound } from "lucide-react";
import { useState } from "react";

import type { TenantFirstAccess } from "../../model/tenants";
import { formatAccountEmailForDisplay } from "../../../../shared/utils/account-email";
import styles from "./TenantAdminCredentialsPanel.module.css";

type CredentialField = "email" | "username" | "password";

interface TenantAdminCredentialsPanelProps {
  access: TenantFirstAccess;
}

export const TenantAdminCredentialsPanel = ({ access }: TenantAdminCredentialsPanelProps) => {
  const [copiedField, setCopiedField] = useState<CredentialField | null>(null);
  const displayEmail = formatAccountEmailForDisplay(access.email);

  const copyValue = async (field: CredentialField, value: string) => {
    try {
      await navigator.clipboard.writeText(value);
      setCopiedField(field);
      window.setTimeout(() => setCopiedField(null), 2000);
    } catch {
      setCopiedField(null);
    }
  };

  const rows: Array<{ field: CredentialField; label: string; value: string }> = [];
  if (displayEmail) {
    rows.push({ field: "email", label: "Work email", value: displayEmail });
  }
  if (access.username) {
    rows.push({ field: "username", label: "Username", value: access.username });
  }
  rows.push({
    field: "password",
    label: "Temporary password",
    value: access.temporary_password,
  });

  const signInHint = displayEmail
    ? "Sign in with work email or username."
    : "Sign in with username.";

  return (
    <div className={styles.panel}>
      <dl className={styles.rows}>
        {rows.map((row) => (
          <div className={styles.row} key={row.field}>
            <dt className={styles.label}>{row.label}</dt>
            <dd className={styles.valueRow}>
              <code>{row.value}</code>
              <button
                type="button"
                className={styles.copyButton}
                onClick={() => void copyValue(row.field, row.value)}
              >
                {copiedField === row.field ? <Check size={14} aria-hidden="true" /> : <Copy size={14} aria-hidden="true" />}
                {copiedField === row.field ? "Copied" : "Copy"}
              </button>
            </dd>
          </div>
        ))}
      </dl>
      {access.password_change_required && (
        <p className={styles.notice}>
          <KeyRound size={15} aria-hidden="true" />
          {signInHint} Password must be changed on first sign-in.
        </p>
      )}
    </div>
  );
};
