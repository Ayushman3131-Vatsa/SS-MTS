import {
  ArrowRight,
  CheckCircle2,
  ClipboardCheck,
  LayoutDashboard,
  PackageCheck,
  SlidersHorizontal,
  UserRound,
  Users,
} from "lucide-react";
import { Link, Navigate } from "react-router-dom";

import { useSession } from "../../entities/session/model/session-context";
import { getPrincipalHome, useTenantAppPath } from "../../entities/session/model/routing";
import { canAccessOffering, canAccessPage } from "../../entities/session/model/page-access";
import styles from "./TenantLandingPage.module.css";

interface TenantLandingPageProps {
  variant: "overview" | "my-work";
}

export const TenantLandingPage = ({ variant }: TenantLandingPageProps) => {
  const { principal } = useSession();
  const appPath = useTenantAppPath();
  if (!principal || principal.principal_type !== "tenant_user") {
    return null;
  }
  const hasNoRoles = !principal.roles || principal.roles.length === 0 || principal.role === "Unassigned";
  const hasOverviewAccess = canAccessPage(principal, "/app/overview");

  // 1. If user has no roles assigned, show a clean white screen
  if (hasNoRoles) {
    return <div className={styles.emptyWhiteScreen} />;
  }

  // 2. If user has roles, but reached /app/overview without overview access, forward to their primary accessible module
  if (!hasOverviewAccess) {
    const home = getPrincipalHome(principal);
    if (!home.endsWith("/app/overview")) {
      return <Navigate to={home} replace />;
    }
    return <div className={styles.emptyWhiteScreen} />;
  }

  const hasTask = canAccessOffering(principal, "TASK_MANAGEMENT") && canAccessPage(principal, "/app/task-management");
  const hasUsers = canAccessPage(principal, "/app/users") || canAccessPage(principal, "/app/roles");
  const hasConfigs = canAccessPage(principal, "/app/configurations");

  return (
    <div className={styles.page}>
      <section className={styles.hero}>
        <span>{variant === "my-work" ? <CheckCircle2 /> : <LayoutDashboard />}</span>
        <p>{principal.tenant.org_name}</p>
        <h1>
          {variant === "my-work"
            ? "You’re securely signed in"
            : "Your workspace is ready"}
        </h1>
        <div>
          Welcome back, {principal.name}. Your portal shows only the modules licensed for this workspace.
        </div>
      </section>
      <section className={styles.cards}>
        <article><UserRound /><span><small>Signed in as</small><strong>{principal.email ?? principal.name}</strong></span></article>
        <article><PackageCheck /><span><small>Licensed offerings</small><strong>{principal.tenant.offerings.length}</strong></span></article>
      </section>
      <h2 className={styles.sectionTitle}>Available modules & shortcuts</h2>
      <div className={styles.moduleGrid}>
        {hasTask && (
          <Link to={appPath("/app/task-management")} className={styles.moduleCard}>
            <div>
              <div className={styles.moduleHeader}>
                <div className={styles.moduleIcon}>
                  <ClipboardCheck size={20} />
                </div>
                <div className={styles.moduleTitle}>Task Management</div>
              </div>
              <p className={styles.moduleDescription}>
                Organize projects, assign tasks, track sprint boards, and monitor team delivery.
              </p>
            </div>
            <div className={styles.moduleAction}>
              <span>Launch Task Management</span>
              <ArrowRight size={15} />
            </div>
          </Link>
        )}
        {hasUsers && (
          <Link to={appPath("/app/users")} className={styles.moduleCard}>
            <div>
              <div className={styles.moduleHeader}>
                <div className={styles.moduleIcon}>
                  <Users size={20} />
                </div>
                <div className={styles.moduleTitle}>User Access Management</div>
              </div>
              <p className={styles.moduleDescription}>
                Manage workspace members, assign custom roles, and configure page access permissions.
              </p>
            </div>
            <div className={styles.moduleAction}>
              <span>Manage Users & Roles</span>
              <ArrowRight size={15} />
            </div>
          </Link>
        )}
        {hasConfigs && (
          <Link to={appPath("/app/configurations")} className={styles.moduleCard}>
            <div>
              <div className={styles.moduleHeader}>
                <div className={styles.moduleIcon}>
                  <SlidersHorizontal size={20} />
                </div>
                <div className={styles.moduleTitle}>Configurations</div>
              </div>
              <p className={styles.moduleDescription}>
                Configure automated email templates, notification triggers, and workspace settings.
              </p>
            </div>
            <div className={styles.moduleAction}>
              <span>Configure Workspace</span>
              <ArrowRight size={15} />
            </div>
          </Link>
        )}
      </div>
    </div>
  );
};
