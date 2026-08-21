import {
  ArrowRight,
  Building2,
  CheckCircle2,
  Clock3,
  LayoutDashboard,
  LogOut,
  ShieldCheck,
  UserRound,
} from "lucide-react";
import { useState } from "react";

import { useSession } from "../../entities/session/model/session-context";
import { getLoginErrorContent } from "../../features/auth/model/login-errors";
import { Alert } from "../../shared/ui/Alert/Alert";
import { BrandMark } from "../../shared/ui/BrandMark/BrandMark";
import { Button } from "../../shared/ui/Button/Button";
import styles from "./ProtectedHomePage.module.css";

type HomeVariant = "platform" | "overview" | "my-work";

interface ProtectedHomePageProps {
  variant: HomeVariant;
}

const content = {
  platform: {
    eyebrow: "Platform console",
    title: "Your platform session is ready",
    description:
      "Tenant registration and platform operations can now be added to this secured foundation.",
    icon: ShieldCheck,
  },
  overview: {
    eyebrow: "Organization workspace",
    title: "Your workspace is ready",
    description:
      "Project overview, people, and tenant administration can now be built on this authenticated shell.",
    icon: LayoutDashboard,
  },
  "my-work": {
    eyebrow: "My work",
    title: "You’re securely signed in",
    description:
      "Assigned tasks and daily work views can now be built on this tenant-scoped experience.",
    icon: CheckCircle2,
  },
} satisfies Record<
  HomeVariant,
  {
    eyebrow: string;
    title: string;
    description: string;
    icon: typeof ShieldCheck;
  }
>;

export const ProtectedHomePage = ({ variant }: ProtectedHomePageProps) => {
  const { logout, principal } = useSession();
  const [isLoggingOut, setIsLoggingOut] = useState(false);
  const [logoutError, setLogoutError] = useState<string | null>(null);
  const page = content[variant];
  const Icon = page.icon;

  if (!principal) {
    return null;
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

  const organization =
    principal.principal_type === "tenant_user"
      ? principal.tenant.org_name
      : "Platform operations";

  return (
    <div className={styles.shell}>
      <header className={styles.topbar}>
        <BrandMark />
        <div className={styles.identity}>
          <div>
            <strong>{organization}</strong>
            <span>{principal.role}</span>
          </div>
          <span className={styles.avatar} aria-hidden="true">
            {principal.name.slice(0, 1).toUpperCase()}
          </span>
          <Button
            variant="ghost"
            onClick={handleLogout}
            loading={isLoggingOut}
            loadingLabel="Signing out…"
            aria-label="Sign out"
          >
            {!isLoggingOut && <LogOut size={17} aria-hidden="true" />}
            {!isLoggingOut && "Sign out"}
          </Button>
        </div>
      </header>

      <main className={styles.content}>
        {logoutError && (
          <Alert tone="error" title="Could not sign out">
            {logoutError}
          </Alert>
        )}

        <section className={styles.hero}>
          <div className={styles.heroIcon}>
            <Icon size={26} aria-hidden="true" />
          </div>
          <p>{page.eyebrow}</p>
          <h1>{page.title}</h1>
          <span>{page.description}</span>
        </section>

        <section className={styles.grid} aria-label="Session summary">
          <article className={styles.card}>
            <div className={styles.cardIcon}>
              <UserRound size={19} aria-hidden="true" />
            </div>
            <div>
              <p>Signed in as</p>
              <h2>{principal.name}</h2>
              <span>{principal.email}</span>
            </div>
          </article>

          <article className={styles.card}>
            <div className={styles.cardIcon}>
              <Building2 size={19} aria-hidden="true" />
            </div>
            <div>
              <p>Access scope</p>
              <h2>{organization}</h2>
              <span>
                {principal.principal_type === "tenant_user"
                  ? principal.tenant.tenant_code
                  : "Cross-tenant platform administration"}
              </span>
            </div>
          </article>

          <article className={styles.card}>
            <div className={styles.cardIcon}>
              <Clock3 size={19} aria-hidden="true" />
            </div>
            <div>
              <p>Session</p>
              <h2>Active and protected</h2>
              <span>Session credentials are stored in an HttpOnly cookie.</span>
            </div>
          </article>
        </section>

        <section className={styles.next}>
          <div>
            <p>Foundation complete</p>
            <h2>Ready for the next product screen</h2>
          </div>
          <ArrowRight size={20} aria-hidden="true" />
        </section>
      </main>
    </div>
  );
};
