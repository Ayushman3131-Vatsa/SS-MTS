import React from "react";
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
  if (!isOpen) return null;

  return (
    <div className={styles.overlay} onClick={onClose}>
      <div
        className={styles.modal}
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-modal="true"
      >
        <div className={styles.header}>
          <div className={styles.headerTitle}>
            <Eye size={18} className={styles.headerIcon} />
            <h3>Live Preview — {title}</h3>
          </div>
          <button type="button" className={styles.closeButton} onClick={onClose}>
            <X size={18} />
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
            <h4>Rendered Preview</h4>

            {subject !== null && (
              <div className={styles.renderedSubject}>
                <strong>Subject:</strong> {subject}
              </div>
            )}

            <div className={styles.renderedBody}>
              <pre className={styles.markdownContent}>{body}</pre>
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
