import styles from "./RouteLoader.module.css";

interface RouteLoaderProps {
  label?: string;
}

export const RouteLoader = ({
  label = "Loading page…",
}: RouteLoaderProps) => (
  <div className={styles.loader} role="status" aria-live="polite">
    <span aria-hidden="true" />
    <p>{label}</p>
  </div>
);

