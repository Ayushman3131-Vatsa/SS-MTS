import type { InputHTMLAttributes, ReactNode } from "react";
import { forwardRef } from "react";

import styles from "./InputField.module.css";

interface InputFieldProps extends InputHTMLAttributes<HTMLInputElement> {
  error?: string;
  hint?: string;
  label: string;
  leadingIcon?: ReactNode;
  trailingControl?: ReactNode;
}

export const InputField = forwardRef<HTMLInputElement, InputFieldProps>(
  (
    {
      className = "",
      error,
      hint,
      id,
      label,
      leadingIcon,
      trailingControl,
      ...props
    },
    ref,
  ) => {
    const descriptionId = error
      ? `${id}-error`
      : hint
        ? `${id}-hint`
        : undefined;

    return (
      <div className={`${styles.field} ${className}`}>
        <label htmlFor={id}>{label}</label>
        <div
          className={`${styles.inputWrap} ${error ? styles.hasError : ""}`}
        >
          {leadingIcon && (
            <span className={styles.leadingIcon} aria-hidden="true">
              {leadingIcon}
            </span>
          )}
          <input
            ref={ref}
            id={id}
            className={`${leadingIcon ? styles.withLeading : ""} ${
              trailingControl ? styles.withTrailing : ""
            }`}
            aria-invalid={Boolean(error)}
            aria-describedby={descriptionId}
            {...props}
          />
          {trailingControl && (
            <span className={styles.trailingControl}>{trailingControl}</span>
          )}
        </div>
        {error ? (
          <p id={`${id}-error`} className={styles.error} role="alert">
            {error}
          </p>
        ) : hint ? (
          <p id={`${id}-hint`} className={styles.hint}>
            {hint}
          </p>
        ) : null}
      </div>
    );
  },
);

InputField.displayName = "InputField";
