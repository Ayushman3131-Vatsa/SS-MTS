import { LockKeyhole, LogOut, ShieldAlert } from "lucide-react";
import { useState } from "react";
import { Navigate } from "react-router-dom";

import { getPrincipalHome } from "../../entities/session/model/routing";
import { useSession } from "../../entities/session/model/session-context";
import { getLoginErrorContent } from "../../features/auth/model/login-errors";
import { BrandMark } from "../../shared/ui/BrandMark/BrandMark";
import { Button } from "../../shared/ui/Button/Button";
import styles from "./SuspendedTenantPage.module.css";

export const SuspendedTenantPage = () => {
  const { logout, principal } = useSession();
  const [isLoggingOut, setIsLoggingOut] = useState(false);
  const [logoutError, setLogoutError] = useState<string | null>(null);

  if (!principal || principal.principal_type !== "tenant_user") {
    return null;
  }

  if (principal.tenant.status === "ACTIVE") {
    return <Navigate to={getPrincipalHome(principal)} replace />;
  }

  const handleLogout = async () => {
    setIsLoggingOut(true);
    setLogoutError(null);
    try {
      await logout();
    } catch (error) {
      setLogoutError(getLoginErrorContent(error).message);
      setIsLoggingOut(false);
    }
  };

  return (
    <div className={styles.page}>
      <header className={styles.topbar}>
        <BrandMark />
        <div className={styles.identity}>
          <span>
            <strong>{principal.name}</strong>
            <small>{principal.email}</small>
          </span>
          <Button
            type="button"
            variant="ghost"
            loading={isLoggingOut}
            loadingLabel="Signing out…"
            onClick={handleLogout}
          >
            <LogOut size={16} aria-hidden="true" />
            Sign out
          </Button>
        </div>
      </header>

      <main className={styles.main}>
        <section className={styles.card} aria-labelledby="suspension-title">
          <span className={styles.icon} aria-hidden="true">
            <ShieldAlert size={30} />
          </span>
          <p className={styles.eyebrow}>Workspace access paused</p>
          <h1 id="suspension-title">Your organization is temporarily suspended</h1>
          <p className={styles.description}>
            You signed in successfully, but <strong>{principal.tenant.org_name}</strong> has
            been suspended by the platform administrator. Workspace features and data are
            unavailable until access is restored.
          </p>

          <div className={styles.statusCard}>
            <LockKeyhole size={18} aria-hidden="true" />
            <div>
              <strong>What happens next?</strong>
              <span>
                Contact your platform administrator. This page checks access automatically
                and will return you to the workspace after reactivation.
              </span>
            </div>
          </div>

          <dl className={styles.workspaceDetails}>
            <div>
              <dt>Tenant code</dt>
              <dd>{principal.tenant.tenant_code}</dd>
            </div>
            <div>
              <dt>Status</dt>
              <dd><span>Suspended</span></dd>
            </div>
          </dl>

          {logoutError && <p className={styles.error} role="alert">{logoutError}</p>}
        </section>
      </main>
    </div>
  );
};
