import { Building2, Fingerprint, LockKeyhole } from "lucide-react";
import type { PropsWithChildren } from "react";

import { BrandMark } from "../../../../shared/ui/BrandMark/BrandMark";
import styles from "./AuthShell.module.css";

interface AuthShellProps extends PropsWithChildren {
  description: string;
  eyebrow: string;
  title: string;
}

export const AuthShell = ({
  children,
  description,
  eyebrow,
  title,
}: AuthShellProps) => (
  <main className={styles.page}>
    <aside className={styles.brandPanel} aria-label="Product overview">
      <div className={styles.brandTop}>
        <BrandMark inverse />
        <span className={styles.secureLabel}>
          <LockKeyhole size={14} aria-hidden="true" />
          Secure access
        </span>
      </div>

      <div className={styles.story}>
        <p className={styles.kicker}>Built for focused organizations</p>
        <h1>One workspace.<br />Every team, correctly isolated.</h1>
        <p>
          A secure, role-aware home for projects, people, and the work that
          moves your organization forward.
        </p>

        <div className={styles.network} aria-hidden="true">
          <span className={`${styles.node} ${styles.nodeA}`}>
            <Building2 size={20} />
          </span>
          <span className={`${styles.node} ${styles.nodeB}`} />
          <span className={`${styles.node} ${styles.nodeC}`} />
          <span className={`${styles.node} ${styles.nodeD}`} />
          <span className={`${styles.line} ${styles.lineA}`} />
          <span className={`${styles.line} ${styles.lineB}`} />
          <span className={`${styles.line} ${styles.lineC}`} />
          <span className={styles.boundary} />
        </div>

        <div className={styles.trustLine}>
          <Fingerprint size={21} aria-hidden="true" />
          <div>
            <strong>Tenant-scoped by design</strong>
            <span>Identity and access stay inside your organization.</span>
          </div>
        </div>
      </div>

      <p className={styles.copyright}>
        © {new Date().getFullYear()} Secure workspace
      </p>
    </aside>

    <section className={styles.formPanel}>
      <div className={styles.mobileBrand}>
        <BrandMark />
        <span>Secure access</span>
      </div>

      <div className={styles.formContainer}>
        <header className={styles.formHeader}>
          <p>{eyebrow}</p>
          <h2>{title}</h2>
          <span>{description}</span>
        </header>
        {children}
      </div>

      <p className={styles.formFooter}>
        Protected by tenant-aware access controls
      </p>
    </section>
  </main>
);
