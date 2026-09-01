import React, { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { SlidersHorizontal, Loader2, AlertCircle, Sparkles } from "lucide-react";

import { useTenantAppPath } from "../../entities/session/model/routing";

import {
  fetchConfigCategories,
  fetchCategoryTemplates,
} from "../../features/configurations/api/configuration-api";
import type {
  ConfigCategoryResponse,
  ConfigTemplateListItem,
} from "../../features/configurations/model/types";
import { CategoryTabs } from "../../features/configurations/ui/CategoryTabs";
import { TemplateCard } from "../../features/configurations/ui/TemplateCard";
import { useWindowFocusRefresh } from "../../shared/model/useWindowFocusRefresh";
import styles from "./ConfigurationsPage.module.css";

export const ConfigurationsPage: React.FC = () => {
  const navigate = useNavigate();
  const appPath = useTenantAppPath();
  const focusRefreshKey = useWindowFocusRefresh();
  const [categories, setCategories] = useState<ConfigCategoryResponse[]>([]);
  const [activeCategoryId, setActiveCategoryId] = useState<string | null>(null);
  const [templates, setTemplates] = useState<ConfigTemplateListItem[]>([]);

  const [loadingCategories, setLoadingCategories] = useState(true);
  const [loadingTemplates, setLoadingTemplates] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // 1. Fetch categories for tenant's licensed offerings
  useEffect(() => {
    let isMounted = true;
    const loadCategories = async () => {
      setLoadingCategories(true);
      setError(null);
      try {
        const data = await fetchConfigCategories();
        if (isMounted) {
          setCategories(data);
          setActiveCategoryId((currentCategoryId) => {
            if (
              currentCategoryId &&
              data.some((category) => category.category_id === currentCategoryId)
            ) {
              return currentCategoryId;
            }
            return data[0]?.category_id ?? null;
          });
        }
      } catch (err) {
        if (isMounted) {
          setError(err instanceof Error ? err.message : "Failed to load configurations");
        }
      } finally {
        if (isMounted) setLoadingCategories(false);
      }
    };

    loadCategories();
    return () => {
      isMounted = false;
    };
  }, [focusRefreshKey]);

  // 2. Fetch templates whenever active category changes
  useEffect(() => {
    if (!activeCategoryId) return;

    let isMounted = true;
    const loadTemplates = async () => {
      setLoadingTemplates(true);
      try {
        const data = await fetchCategoryTemplates(activeCategoryId);
        if (isMounted) setTemplates(data);
      } catch (err) {
        if (isMounted) {
          setError(err instanceof Error ? err.message : "Failed to load templates");
        }
      } finally {
        if (isMounted) setLoadingTemplates(false);
      }
    };

    loadTemplates();
    return () => {
      isMounted = false;
    };
  }, [activeCategoryId, focusRefreshKey]);

  const activeCategory = categories.find((c) => c.category_id === activeCategoryId);

  return (
    <div className={styles.page}>
      <header className={styles.pageHeader}>
        <div className={styles.headerTitle}>
          <SlidersHorizontal size={24} className={styles.headerIcon} />
          <div>
            <h1>Workspace Configurations</h1>
            <p>Customize email templates, letter formats, and notifications per licensed module.</p>
          </div>
        </div>
      </header>

      {error && (
        <div className={styles.errorBox} role="alert">
          <AlertCircle size={18} />
          <span>{error}</span>
        </div>
      )}

      {loadingCategories ? (
        <div className={styles.loadingState}>
          <Loader2 size={24} className={styles.spinner} />
          <span>Loading configuration categories…</span>
        </div>
      ) : categories.length === 0 ? (
        <div className={styles.emptyCategoriesState}>
          <Sparkles size={32} />
          <h3>No Licensed Modules Configurable</h3>
          <p>Your organization currently has no active modules that support configuration templates.</p>
        </div>
      ) : (
        <div className={styles.grid}>
          {/* Sidebar Tabs */}
          <aside className={styles.sidebar}>
            <CategoryTabs
              categories={categories}
              activeCategoryId={activeCategoryId}
              onSelectCategory={setActiveCategoryId}
            />
          </aside>

          {/* Main Content Area */}
          <main className={styles.content}>
            {activeCategory && (
              <div className={styles.categoryHeader}>
                <div>
                  <h2>{activeCategory.display_name}</h2>
                  <p className={styles.categoryDesc}>{activeCategory.description}</p>
                </div>
                <span className={styles.offeringTag}>{activeCategory.offering_display_name}</span>
              </div>
            )}

            {loadingTemplates ? (
              <div className={styles.loadingState}>
                <Loader2 size={20} className={styles.spinner} />
                <span>Loading templates…</span>
              </div>
            ) : templates.length === 0 ? (
              <div className={styles.emptyTemplatesState}>
                <p>No templates found in this category.</p>
              </div>
            ) : (
              <div className={styles.templateList}>
                {templates.map((template) => (
                  <TemplateCard
                    key={template.template_id}
                    template={template}
                    onSelect={(id) => navigate(appPath(`/app/configurations/templates/${id}`))}
                  />
                ))}
              </div>
            )}
          </main>
        </div>
      )}
    </div>
  );
};
