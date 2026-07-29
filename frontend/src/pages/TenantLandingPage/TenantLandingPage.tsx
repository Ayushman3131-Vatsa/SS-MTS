import { ArrowRight, CheckCircle2, LayoutDashboard, PackageCheck, UserRound } from "lucide-react";
import { Link } from "react-router-dom";

import { useSession } from "../../entities/session/model/session-context";
import styles from "./TenantLandingPage.module.css";

interface TenantLandingPageProps {
  variant: "overview" | "my-work";
}

export const TenantLandingPage = ({ variant }: TenantLandingPageProps) => {
  const { principal } = useSession();
  if (!principal || principal.principal_type !== "tenant_user") {
    return null;
  }
  const firstOffering = principal.tenant.offerings[0];
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
        <article><UserRound /><span><small>Signed in as</small><strong>{principal.email}</strong></span></article>
        <article><PackageCheck /><span><small>Licensed offerings</small><strong>{principal.tenant.offerings.length}</strong></span></article>
      </section>
      {firstOffering && (
        <Link to={`/app/modules/${firstOffering.route_slug}`}>
          <span><small>Explore your modules</small><strong>{firstOffering.display_name}</strong></span>
          <ArrowRight />
        </Link>
      )}
    </div>
  );
};
