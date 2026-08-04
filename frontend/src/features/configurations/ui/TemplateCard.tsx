import React from "react";
import { Mail, FileText, Bell, ChevronRight, CheckCircle2, SlidersHorizontal } from "lucide-react";
import type { ConfigTemplateListItem } from "../model/types";
import styles from "./TemplateCard.module.css";

interface TemplateCardProps {
  template: ConfigTemplateListItem;
  onSelect: (templateId: string) => void;
}

const typeIconMap: Record<string, React.ElementType> = {
  EMAIL: Mail,
  LETTER: FileText,
  NOTIFICATION: Bell,
};

export const TemplateCard: React.FC<TemplateCardProps> = ({ template, onSelect }) => {
  const Icon = typeIconMap[template.template_type] || FileText;

  return (
    <div
      className={styles.card}
      onClick={() => onSelect(template.template_id)}
      role="button"
      tabIndex={0}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") {
          onSelect(template.template_id);
        }
      }}
    >
      <div className={styles.iconWrapper}>
        <Icon size={20} className={styles.typeIcon} />
      </div>

      <div className={styles.content}>
        <div className={styles.header}>
          <h4 className={styles.title}>{template.display_name}</h4>
          <span className={styles.typeBadge}>{template.template_type}</span>
          {template.is_customized ? (
            <span className={`${styles.statusBadge} ${styles.customizedBadge}`}>
              <SlidersHorizontal size={12} />
              Customized
            </span>
          ) : (
            <span className={`${styles.statusBadge} ${styles.defaultBadge}`}>
              <CheckCircle2 size={12} />
              Platform Default
            </span>
          )}
        </div>
        <p className={styles.description}>{template.description}</p>
        {template.subject && (
          <div className={styles.subjectPreview}>
            <strong>Subject:</strong> {template.subject}
          </div>
        )}
      </div>

      <ChevronRight size={18} className={styles.arrowIcon} />
    </div>
  );
};
