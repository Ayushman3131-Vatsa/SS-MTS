import React from "react";
import { Mail, FileText, Bell, Sparkles } from "lucide-react";
import type { ConfigCategoryResponse } from "../model/types";
import styles from "./CategoryTabs.module.css";

interface CategoryTabsProps {
  categories: ConfigCategoryResponse[];
  activeCategoryId: string | null;
  onSelectCategory: (categoryId: string) => void;
}

const iconMap: Record<string, React.ElementType> = {
  mail: Mail,
  "file-text": FileText,
  bell: Bell,
};

export const CategoryTabs: React.FC<CategoryTabsProps> = ({
  categories,
  activeCategoryId,
  onSelectCategory,
}) => {
  // Group categories by offering
  const groupedByOffering = categories.reduce<
    Record<string, { offeringName: string; categories: ConfigCategoryResponse[] }>
  >((acc, cat) => {
    if (!acc[cat.offering_id]) {
      acc[cat.offering_id] = {
        offeringName: cat.offering_display_name,
        categories: [],
      };
    }
    acc[cat.offering_id].categories.push(cat);
    return acc;
  }, {});

  return (
    <div className={styles.container}>
      {Object.entries(groupedByOffering).map(([offeringId, group]) => (
        <div key={offeringId} className={styles.offeringGroup}>
          <div className={styles.offeringHeader}>
            <Sparkles size={14} className={styles.offeringIcon} />
            <span>{group.offeringName}</span>
          </div>
          <div className={styles.tabList}>
            {group.categories.map((cat) => {
              const IconComponent = iconMap[cat.icon_key] || FileText;
              const isActive = cat.category_id === activeCategoryId;
              return (
                <button
                  key={cat.category_id}
                  type="button"
                  className={`${styles.tab} ${isActive ? styles.activeTab : ""}`}
                  onClick={() => onSelectCategory(cat.category_id)}
                >
                  <IconComponent size={16} />
                  <span className={styles.tabTitle}>{cat.display_name}</span>
                  <span className={styles.badge}>{cat.template_count}</span>
                </button>
              );
            })}
          </div>
        </div>
      ))}
    </div>
  );
};
