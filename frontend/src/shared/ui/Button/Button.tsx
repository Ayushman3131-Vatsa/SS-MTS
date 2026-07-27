import type { ButtonHTMLAttributes, PropsWithChildren } from "react";

import styles from "./Button.module.css";

type ButtonVariant = "primary" | "secondary" | "ghost";

interface ButtonProps
  extends PropsWithChildren<ButtonHTMLAttributes<HTMLButtonElement>> {
  fullWidth?: boolean;
  loading?: boolean;
  loadingLabel?: string;
  variant?: ButtonVariant;
}

export const Button = ({
  children,
  className = "",
  disabled,
  fullWidth = false,
  loading = false,
  loadingLabel = "Please wait…",
  variant = "primary",
  ...props
}: ButtonProps) => (
  <button
    className={`${styles.button} ${styles[variant]} ${
      fullWidth ? styles.fullWidth : ""
    } ${className}`}
    disabled={disabled || loading}
    aria-busy={loading}
    {...props}
  >
    {loading && <span className={styles.spinner} aria-hidden="true" />}
    <span>{loading ? loadingLabel : children}</span>
  </button>
);
