import {
  Bell,
  FileStack,
  FileText,
  Mail,
  Package,
  Plus,
  RefreshCw,
  Search,
  Users,
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";

import { defaultTemplatesApi } from "../../features/default-template-management/api/default-templates-api";
import {
  DEFAULT_TEMPLATE_TYPES,
  type DefaultTemplateType,
} from "../../features/default-template-management/model/default-templates";
import type { DefaultTemplateListItem } from "../../features/default-template-management/model/default-templates";
import { offeringsApi } from "../../features/offering-management/api/offerings-api";
import type { OfferingCatalogItem } from "../../features/offering-management/model/offerings";
import { Alert } from "../../shared/ui/Alert/Alert";
import { Button } from "../../shared/ui/Button/Button";
import styles from "./DefaultTemplatesPage.module.css";

const typeLabels: Record<DefaultTemplateType, string> = {
  EMAIL: "Email",
  LETTER: "Letter",
  NOTIFICATION: "Notification",
  OTHER: "Other",
};

const typeIcons = {
  EMAIL: Mail,
  LETTER: FileText,
  NOTIFICATION: Bell,
  OTHER: FileStack,
} as const;

const isTemplateType = (value: string | null): value is DefaultTemplateType =>
  DEFAULT_TEMPLATE_TYPES.some((type) => type === value);

const templateMatches = (template: DefaultTemplateListItem, query: string) => {
  const normalized = query.trim().toLowerCase();
  if (!normalized) return true;
  return [
    template.name,
    template.code,
    template.description,
    template.category_name,
    template.offering_name,
  ].some((value) => value.toLowerCase().includes(normalized));
};

export const DefaultTemplatesPage = () => {
  const [searchParams, setSearchParams] = useSearchParams();
  const offeringId = searchParams.get("offering_id") ?? "";
  const typeParam = searchParams.get("type");
  const selectedType = isTemplateType(typeParam) ? typeParam : "";
  const [offerings, setOfferings] = useState<OfferingCatalogItem[] | null>(null);
  const [templates, setTemplates] = useState<DefaultTemplateListItem[] | null>(null);
  const [offeringQuery, setOfferingQuery] = useState("");
  const [templateQuery, setTemplateQuery] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [refreshKey, setRefreshKey] = useState(0);
  const offeringsLoading = offerings === null;
  const offeringSelectionValid = offerings?.some((offering) => offering.offering_id === offeringId) ?? false;

  useEffect(() => {
    const controller = new AbortController();
    void offeringsApi.list(controller.signal).then((result) => {
      setOfferings(result);
    }).catch((requestError: unknown) => {
      if (requestError instanceof DOMException && requestError.name === "AbortError") return;
      setError(requestError instanceof Error ? requestError.message : "Offerings could not be loaded.");
      setOfferings([]);
    });
    return () => controller.abort();
  }, [refreshKey]);

  useEffect(() => {
    if (!offerings?.length) return;
    const hasValidOffering = offerings.some((offering) => offering.offering_id === offeringId);
    if (hasValidOffering) return;
    const next = new URLSearchParams(searchParams);
    next.set("offering_id", offerings[0].offering_id);
    setSearchParams(next, { replace: true });
  }, [offeringId, offerings, searchParams, setSearchParams]);

  useEffect(() => {
    if (offeringsLoading) {
      setTemplates(null);
      return;
    }
    if (!offeringId || !offeringSelectionValid) {
      setTemplates([]);
      return;
    }
    const controller = new AbortController();
    setTemplates(null);
    setError(null);
    void defaultTemplatesApi.list({
      offeringId,
      signal: controller.signal,
    }).then(setTemplates).catch((requestError: unknown) => {
      if (requestError instanceof DOMException && requestError.name === "AbortError") return;
      setError(requestError instanceof Error ? requestError.message : "Default templates could not be loaded.");
      setTemplates([]);
    });
    return () => controller.abort();
  }, [offeringId, offeringSelectionValid, offeringsLoading, refreshKey]);

  const updateFilter = (key: "offering_id" | "type", value: string) => {
    const next = new URLSearchParams(searchParams);
    if (value) next.set(key, value);
    else next.delete(key);
    setSearchParams(next, { replace: true });
  };

  const visibleOfferings = useMemo(() => {
    const normalized = offeringQuery.trim().toLowerCase();
    return [...(offerings ?? [])]
      .filter((offering) => !normalized || `${offering.display_name} ${offering.code}`.toLowerCase().includes(normalized))
      .sort((left, right) => left.sort_order - right.sort_order || left.display_name.localeCompare(right.display_name));
  }, [offeringQuery, offerings]);

  const visibleTemplates = useMemo(() => (templates ?? []).filter((template) =>
    (!selectedType || template.type === selectedType) && templateMatches(template, templateQuery)
  ), [selectedType, templateQuery, templates]);

  const selectedOffering = offerings?.find((offering) => offering.offering_id === offeringId);
  const inheritingCount = visibleTemplates.reduce((sum, item) => sum + item.inheriting_tenant_count, 0);
  const customizedCount = visibleTemplates.reduce((sum, item) => sum + item.customized_tenant_count, 0);
  const createParams = new URLSearchParams();
  if (offeringId) createParams.set("offering_id", offeringId);
  if (selectedType) createParams.set("type", selectedType);
  const createSearch = createParams.size > 0 ? `?${createParams.toString()}` : "";

  return (
    <div className={styles.page}>
      <header className={styles.pageHeader}>
        <div>
          <p>Platform configuration</p>
          <h1>Default templates</h1>
          <span>Manage the source templates inherited by tenant workspaces.</span>
        </div>
        <Link className={styles.createLink} to={`/platform/default-templates/new${createSearch}`}>
          <Plus size={17} aria-hidden="true" />
          New default template
        </Link>
      </header>

      {error && <Alert tone="error" title="Catalog unavailable">{error}</Alert>}

      <div className={styles.workspace}>
        <aside className={styles.offeringPanel} aria-label="Filter by offering">
          <div className={styles.panelHeading}>
            <div>
              <span>Catalog</span>
              <h2>Offerings</h2>
            </div>
            <Package size={18} aria-hidden="true" />
          </div>
          <label className={styles.searchField}>
            <Search size={15} aria-hidden="true" />
            <span className={styles.srOnly}>Search offerings</span>
            <input
              value={offeringQuery}
              onChange={(event) => setOfferingQuery(event.target.value)}
              placeholder="Search offerings"
            />
          </label>
          <div className={styles.offeringList}>
            {visibleOfferings.map((offering) => (
              <button
                type="button"
                key={offering.offering_id}
                className={offeringId === offering.offering_id ? styles.selectedOffering : ""}
                aria-pressed={offeringId === offering.offering_id}
                onClick={() => updateFilter("offering_id", offering.offering_id)}
              >
                <span className={styles.offeringIcon}><Package size={16} aria-hidden="true" /></span>
                <span>
                  <strong>{offering.display_name}</strong>
                  <small>{offering.code}</small>
                </span>
                {offering.status === "INACTIVE" && <em>Inactive</em>}
              </button>
            ))}
            {offerings !== null && visibleOfferings.length === 0 && (
              <p className={styles.emptyOfferings}>No offerings match your search.</p>
            )}
          </div>
        </aside>

        <main className={styles.catalog}>
          <div className={styles.catalogHeader}>
            <div>
              <p>{selectedOffering ? selectedOffering.code : "PLATFORM"}</p>
              <h2>{selectedOffering?.display_name ?? "All default templates"}</h2>
              <span>{selectedOffering?.description ?? "Defaults across every current and future offering."}</span>
            </div>
            {selectedOffering?.status === "INACTIVE" && <span className={styles.inactiveBadge}>Inactive offering</span>}
          </div>

          <div className={styles.metrics} aria-label="Visible template impact">
            <div><FileStack size={18} aria-hidden="true" /><span><strong>{visibleTemplates.length}</strong> templates</span></div>
            <div><Users size={18} aria-hidden="true" /><span><strong>{inheritingCount}</strong> inheriting</span></div>
            <div><Users size={18} aria-hidden="true" /><span><strong>{customizedCount}</strong> customized</span></div>
          </div>

          <div className={styles.toolbar}>
            <label className={styles.searchField}>
              <Search size={16} aria-hidden="true" />
              <span className={styles.srOnly}>Search templates</span>
              <input
                value={templateQuery}
                onChange={(event) => setTemplateQuery(event.target.value)}
                placeholder="Search name, code, or category"
              />
            </label>
            <div className={styles.typeFilters} role="group" aria-label="Filter templates by type">
              <button type="button" aria-pressed={!selectedType} onClick={() => updateFilter("type", "")}>All</button>
              {DEFAULT_TEMPLATE_TYPES.map((type) => (
                <button type="button" key={type} aria-pressed={selectedType === type} onClick={() => updateFilter("type", type)}>
                  {typeLabels[type]}
                </button>
              ))}
            </div>
            <Button
              type="button"
              variant="ghost"
              aria-label="Refresh default templates"
              onClick={() => setRefreshKey((value) => value + 1)}
            >
              <RefreshCw size={16} aria-hidden="true" />
            </Button>
          </div>

          {templates === null ? (
            <div className={styles.loadingState} role="status">Loading default templates&hellip;</div>
          ) : visibleTemplates.length === 0 ? (
            <div className={styles.emptyState}>
              <FileStack size={28} aria-hidden="true" />
              <h3>No templates match these filters</h3>
              <p>Try another offering or type, or create a new platform default.</p>
            </div>
          ) : (
            <div className={styles.templateList}>
              {visibleTemplates.map((template) => {
                const Icon = typeIcons[template.type];
                return (
                  <Link key={template.template_id} to={`/platform/default-templates/${template.template_id}`}>
                    <span className={styles.typeIcon}><Icon size={18} aria-hidden="true" /></span>
                    <span className={styles.templateIdentity}>
                      <span><strong>{template.name}</strong><em>{typeLabels[template.type]}</em>{!template.is_active && <em className={styles.draftBadge}>Inactive</em>}</span>
                      <small>{template.category_name} &middot; {template.code}</small>
                      <p>{template.description}</p>
                    </span>
                    <span className={styles.impact}>
                      <strong>{template.inheriting_tenant_count}</strong>
                      <small>inherit</small>
                    </span>
                    <span className={styles.impact}>
                      <strong>{template.customized_tenant_count}</strong>
                      <small>customized</small>
                    </span>
                    <span className={styles.version}>v{template.version}</span>
                  </Link>
                );
              })}
            </div>
          )}
        </main>
      </div>
    </div>
  );
};
