import { AlertCircle, CheckCircle2, Info } from "lucide-react";
import type { PropsWithChildren } from "react";

import styles from "./Alert.module.css";

type AlertTone = "error" | "info" | "success" | "warning";

interface AlertProps extends PropsWithChildren {
  tone?: AlertTone;
  title?: string;
}

const icons = {
  error: AlertCircle,
  info: Info,
  success: CheckCircle2,
  warning: AlertCircle,
};

export const Alert = ({
  children,
  title,
  tone = "info",
}: AlertProps) => {
  const Icon = icons[tone];

  return (
    <div
      className={`${styles.alert} ${styles[tone]}`}
      role={tone === "error" ? "alert" : "status"}
      aria-live={tone === "error" ? "assertive" : "polite"}
    >
      <Icon size={18} strokeWidth={2} aria-hidden="true" />
      <div>
        {title && <strong>{title}</strong>}
        <div>{children}</div>
      </div>
    </div>
  );
};
