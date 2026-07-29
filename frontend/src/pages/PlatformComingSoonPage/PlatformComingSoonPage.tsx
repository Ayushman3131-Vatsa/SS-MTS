import { ArrowLeft, Building2, PlusCircle } from "lucide-react";
import { Link } from "react-router-dom";

import styles from "./PlatformComingSoonPage.module.css";

interface PlatformComingSoonPageProps {
  variant: "tenants" | "register";
}

const content = {
  tenants: {
    description:
      "Tenant search, status filters, subscription details, and management actions will live here.",
    icon: Building2,
    title: "All Tenants",
  },
  register: {
    description:
      "The guided tenant and Tenant Admin registration workflow is planned for the next release.",
    icon: PlusCircle,
    title: "Register Tenant",
  },
} as const;

export const PlatformComingSoonPage = ({
  variant,
}: PlatformComingSoonPageProps) => {
  const page = content[variant];
  const Icon = page.icon;

  return (
    <div className={styles.page}>
      <section className={styles.card}>
        <span className={styles.icon}>
          <Icon size={24} aria-hidden="true" />
        </span>
        <p>Coming next</p>
        <h1>{page.title}</h1>
        <span>{page.description}</span>
        <Link to="/platform">
          <ArrowLeft size={16} aria-hidden="true" />
          Back to Dashboard
        </Link>
      </section>
    </div>
  );
};

