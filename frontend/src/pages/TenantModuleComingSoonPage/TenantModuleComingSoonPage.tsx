import { ArrowLeft, Clock3, PackageCheck } from "lucide-react";
import { Link, Navigate, useParams } from "react-router-dom";

import { useSession } from "../../entities/session/model/session-context";
import { getPrincipalHome } from "../../entities/session/model/routing";
import styles from "./TenantModuleComingSoonPage.module.css";

export const TenantModuleComingSoonPage = () => {
  const { moduleSlug } = useParams();
  const { principal } = useSession();
  if (!principal || principal.principal_type !== "tenant_user") {
    return null;
  }
  const offering = principal.tenant.offerings.find(
    (candidate) => candidate.route_slug === moduleSlug,
  );
  if (!offering) {
    return <Navigate to="/forbidden" replace />;
  }
  return (
    <div className={styles.page}>
      <Link to={getPrincipalHome(principal)}><ArrowLeft size={15} /> Workspace overview</Link>
      <section>
        <span><PackageCheck size={24} /></span>
        <p>Licensed module</p>
        <h1>{offering.display_name}</h1>
        <div>{offering.description}</div>
        <aside><Clock3 size={16} /><strong>Coming soon</strong> — this module is licensed and ready for its product workflow.</aside>
      </section>
    </div>
  );
};
