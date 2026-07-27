import { ArrowLeft, ShieldX } from "lucide-react";
import { Link } from "react-router-dom";

import { getPrincipalHome } from "../../entities/session/model/routing";
import { useSession } from "../../entities/session/model/session-context";
import { BrandMark } from "../../shared/ui/BrandMark/BrandMark";
import styles from "./ForbiddenPage.module.css";

export const ForbiddenPage = () => {
  const { principal } = useSession();
  const destination = principal ? getPrincipalHome(principal) : "/login";

  return (
    <main className={styles.page}>
      <BrandMark />
      <div className={styles.icon}>
        <ShieldX size={28} aria-hidden="true" />
      </div>
      <p>Access boundary</p>
      <h1>This area isn’t available for your role</h1>
      <span>
        Your account is signed in, but this route belongs to a different
        workspace or role.
      </span>
      <Link to={destination}>
        <ArrowLeft size={17} aria-hidden="true" />
        Return to your workspace
      </Link>
    </main>
  );
};
