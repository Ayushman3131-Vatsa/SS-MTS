import React, { useEffect, useRef } from "react";
import { X, Eye } from "lucide-react";
import styles from "./TemplatePreviewModal.module.css";

interface TemplatePreviewModalProps {
  isOpen: boolean;
  onClose: () => void;
  title: string;
  subject: string | null;
  body: string;
  sampleData: Record<string, string>;
  onSampleDataChange: (key: string, value: string) => void;
}

export const TemplatePreviewModal: React.FC<TemplatePreviewModalProps> = ({
  isOpen,
  onClose,
  title,
  subject,
  body,
  sampleData,
  onSampleDataChange,
}) => {
  const modalRef = useRef<HTMLDivElement>(null);
  const closeButtonRef = useRef<HTMLButtonElement>(null);
  const onCloseRef = useRef(onClose);

  useEffect(() => {
    onCloseRef.current = onClose;
  }, [onClose]);

  useEffect(() => {
    if (!isOpen) return;
    const previouslyFocused = document.activeElement as HTMLElement | null;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    closeButtonRef.current?.focus();
    const containKeyboardFocus = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        onCloseRef.current();
        return;
      }
      if (event.key !== "Tab") return;
      const focusable = Array.from(modalRef.current?.querySelectorAll<HTMLElement>(
        "button:not([disabled]), input:not([disabled]), [href], [tabindex]:not([tabindex='-1'])",
      ) ?? []);
      if (focusable.length === 0) {
        event.preventDefault();
        return;
      }
      const first = focusable[0];
      const last = focusable.at(-1);
      const focusIsOutside = !modalRef.current?.contains(document.activeElement);
      if (event.shiftKey && (document.activeElement === first || focusIsOutside)) {
        event.preventDefault();
        last?.focus();
      } else if (!event.shiftKey && (document.activeElement === last || focusIsOutside)) {
        event.preventDefault();
        first?.focus();
      }
    };
    document.addEventListener("keydown", containKeyboardFocus);
    return () => {
      document.removeEventListener("keydown", containKeyboardFocus);
      document.body.style.overflow = previousOverflow;
      previouslyFocused?.focus();
    };
  }, [isOpen]);

  if (!isOpen) return null;

  return (
    <div className={styles.overlay} onClick={onClose}>
      <div
        ref={modalRef}
        className={styles.modal}
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-modal="true"
        aria-labelledby="template-preview-title"
      >
        <div className={styles.header}>
          <div className={styles.headerTitle}>
            <Eye size={18} className={styles.headerIcon} />
            <h3 id="template-preview-title">Live Preview — {title}</h3>
          </div>
          <button ref={closeButtonRef} type="button" className={styles.closeButton} onClick={onClose} aria-label="Close template preview">
            <X size={18} aria-hidden="true" />
          </button>
        </div>

        <div className={styles.bodyGrid}>
          {/* Left panel: Sample data inputs */}
          <div className={styles.sampleDataPanel}>
            <h4>Sample Variables</h4>
            <p className={styles.subtext}>
              Modify sample values to test dynamic placeholders in real time:
            </p>

            <div className={styles.fieldList}>
              {Object.keys(sampleData).length === 0 ? (
                <p className={styles.emptyText}>No placeholders defined for this template.</p>
              ) : (
                Object.entries(sampleData).map(([key, value]) => (
                  <div key={key} className={styles.field}>
                    <label htmlFor={`sample-${key}`}>
                      <code>{`{{${key}}}`}</code>
                    </label>
                    <input
                      id={`sample-${key}`}
                      type="text"
                      value={value}
                      onChange={(e) => onSampleDataChange(key, e.target.value)}
                    />
                  </div>
                ))
              )}
            </div>
          </div>

          {/* Right panel: Rendered Output */}
          <div className={styles.renderedPanel}>
            <h4>Placeholder Preview</h4>
            <p className={styles.sourceNote}>
              Dynamic values are resolved; Markdown formatting is shown as source.
            </p>

            {subject !== null && (
              <div className={styles.renderedSubject}>
                <strong>Subject:</strong> {subject}
              </div>
            )}

            <div className={styles.renderedBody}>
              <pre className={styles.markdownContent} aria-label="Rendered Markdown source">{body}</pre>
            </div>
          </div>
        </div>

        <div className={styles.footer}>
          <button type="button" className={styles.doneButton} onClick={onClose}>
            Done
          </button>
        </div>
      </div>
    </div>
  );
};
