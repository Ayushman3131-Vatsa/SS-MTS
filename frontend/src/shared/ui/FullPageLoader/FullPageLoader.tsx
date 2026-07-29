import { BrandMark } from "../BrandMark/BrandMark";
import styles from "./FullPageLoader.module.css";

export const FullPageLoader = () => (
  <main className={styles.page} aria-busy="true" aria-live="polite">
    <BrandMark />
    <span className={styles.spinner} aria-hidden="true" />
    <p>Verifying your secure session…</p>
  </main>
);
