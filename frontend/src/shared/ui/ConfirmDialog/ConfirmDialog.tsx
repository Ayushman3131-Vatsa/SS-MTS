import { AlertTriangle, X } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import { Button } from "../Button/Button";
import styles from "./ConfirmDialog.module.css";

interface ConfirmDialogProps {
  open: boolean;
  title: string;
  description: string;
  confirmLabel: string;
  cancelLabel?: string;
  destructive?: boolean;
  reason?: string;
  reasonLabel?: string;
  reasonPlaceholder?: string;
  reasonRequired?: boolean;
  busy?: boolean;
  onReasonChange?: (value: string) => void;
  onCancel: () => void;
  onConfirm: () => void;
}

export const ConfirmDialog = ({
  open,
  title,
  description,
  confirmLabel,
  cancelLabel = "Cancel",
  destructive = false,
  reason = "",
  reasonLabel = "Reason (optional)",
  reasonPlaceholder = "Add an internal note",
  reasonRequired = false,
  busy = false,
  onReasonChange,
  onCancel,
  onConfirm,
}: ConfirmDialogProps) => {
  const confirmRef = useRef<HTMLButtonElement>(null);
  const previouslyFocused = useRef<HTMLElement | null>(null);
  const [reasonError, setReasonError] = useState(false);

  useEffect(() => {
    if (!open) return;
    previouslyFocused.current = document.activeElement as HTMLElement | null;
    setReasonError(false);
    confirmRef.current?.focus();

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape" && !busy) onCancel();
    };
    document.addEventListener("keydown", handleKeyDown);

    return () => {
      document.removeEventListener("keydown", handleKeyDown);
      previouslyFocused.current?.focus();
    };
  }, [busy, onCancel, open]);

  if (!open) return null;

  const handleConfirm = () => {
    if (reasonRequired && !reason.trim()) {
      setReasonError(true);
      return;
    }
    onConfirm();
  };

  return (
    <div className={styles.backdrop} role="presentation">
      <section
        className={styles.dialog}
        role="dialog"
        aria-modal="true"
        aria-labelledby="confirmation-dialog-title"
        aria-describedby="confirmation-dialog-description"
      >
        <div className={styles.header}>
          <div className={`${styles.icon} ${destructive ? styles.destructive : ""}`} aria-hidden="true">
            <AlertTriangle size={19} />
          </div>
          <button className={styles.close} type="button" onClick={onCancel} disabled={busy} aria-label="Close confirmation dialog">
            <X size={18} />
          </button>
        </div>
        <h2 id="confirmation-dialog-title">{title}</h2>
        <p id="confirmation-dialog-description">{description}</p>
        {onReasonChange && (
          <label className={styles.reason}>
            <span>{reasonLabel}{reasonRequired ? " *" : ""}</span>
            <textarea
              value={reason}
              onChange={(event) => {
                onReasonChange(event.target.value);
                if (event.target.value.trim()) setReasonError(false);
              }}
              placeholder={reasonPlaceholder}
              aria-invalid={reasonError}
              aria-describedby={reasonError ? "confirmation-dialog-reason-error" : undefined}
              rows={3}
            />
            {reasonError && <small id="confirmation-dialog-reason-error">A reason is required.</small>}
          </label>
        )}
        <div className={styles.actions}>
          <Button type="button" variant="secondary" onClick={onCancel} disabled={busy}>{cancelLabel}</Button>
          <Button ref={confirmRef} type="button" onClick={handleConfirm} loading={busy} className={destructive ? styles.dangerButton : ""}>
            {confirmLabel}
          </Button>
        </div>
      </section>
    </div>
  );
};
