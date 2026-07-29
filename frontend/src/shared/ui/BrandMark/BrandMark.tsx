import styles from "./BrandMark.module.css";

interface BrandMarkProps {
  compact?: boolean;
  inverse?: boolean;
}

const appName = import.meta.env.VITE_APP_NAME?.trim() || "Workspace";

export const BrandMark = ({
  compact = false,
  inverse = false,
}: BrandMarkProps) => (
  <div
    className={`${styles.brand} ${inverse ? styles.inverse : ""}`}
    aria-label={appName}
  >
    <span className={styles.symbol} aria-hidden="true">
      <span />
      <span />
      <span />
    </span>
    {!compact && <span className={styles.name}>{appName}</span>}
  </div>
);
