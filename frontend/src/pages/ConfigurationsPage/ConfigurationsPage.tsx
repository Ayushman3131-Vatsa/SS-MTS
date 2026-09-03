import { Eye, FileStack, Pencil, Search } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";

import { useTenantAppPath } from "../../entities/session/model/routing";
import {
  fetchConfigCategories,
  fetchConfigTemplates,
  fetchTemplateDetail,
  previewTemplate,
} from "../../features/configurations/api/configuration-api";
import type {
  ConfigCategoryResponse,
  ConfigTemplateCatalogItem,
  ConfigTemplateDetailResponse,
  ConfigTemplateType,
} from "../../features/configurations/model/types";
import { TemplatePreviewModal } from "../../features/configurations/ui/TemplatePreviewModal";
import { useWindowFocusRefresh } from "../../shared/model/useWindowFocusRefresh";
import { Alert } from "../../shared/ui/Alert/Alert";
import styles from "./ConfigurationsPage.module.css";

const typeLabels: Record<ConfigTemplateType, string> = {
  EMAIL: "Email",
  NOTIFICATION: "Notification",
  LETTER: "Letter",
  OTHER: "Other",
};

const formatOptions: ConfigTemplateType[] = [
  "EMAIL",
  "NOTIFICATION",
  "LETTER",
  "OTHER",
];

const dateFormatter = new Intl.DateTimeFormat("en-US", {
  month: "short",
  day: "numeric",
  year: "numeric",
});

const isTemplateType = (value: string | null): value is ConfigTemplateType =>
  formatOptions.some((type) => type === value);

const templateMatches = (template: ConfigTemplateCatalogItem, query: string) => {
  const normalized = query.trim().toLowerCase();
  if (!normalized) return true;
  return [
    template.display_name,
    template.code,
    template.description,
    template.category_name,
    template.offering_name,
  ].some((value) => value.toLowerCase().includes(normalized));
};

const formatCreatedAt = (value: string) => {
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? "—" : dateFormatter.format(date);
};

const sampleValues = (template: ConfigTemplateDetailResponse) => Object.fromEntries(
  template.placeholders.map((placeholder) => [placeholder.key, placeholder.sample_value || ""]),
);

const renderEffectiveTemplate = (
  template: ConfigTemplateDetailResponse,
  samples: Record<string, string>,
) => {
  let subject = template.subject;
  let body = template.body;
  template.placeholders.forEach((placeholder) => {
    const token = `{{${placeholder.key}}}`;
    const value = samples[placeholder.key] ?? placeholder.sample_value;
    subject = subject?.split(token).join(value) ?? null;
    body = body.split(token).join(value);
  });
  return { subject, body };
};

interface OfferingOption {
  id: string;
  name: string;
  sortOrder: number;
}

const offeringOptions = (categories: ConfigCategoryResponse[]): OfferingOption[] => {
  const options = new Map<string, OfferingOption>();
  categories.forEach((category) => {
    const current = options.get(category.offering_id);
    const next = {
      id: category.offering_id,
      name: category.offering_display_name,
      sortOrder: category.sort_order,
    };
    if (!current || next.sortOrder < current.sortOrder) options.set(category.offering_id, next);
  });
  return [...options.values()].sort(
    (left, right) => left.sortOrder - right.sortOrder || left.name.localeCompare(right.name),
  );
};

export const ConfigurationsPage = () => {
  const appPath = useTenantAppPath();
  const focusRefreshKey = useWindowFocusRefresh();
  const [searchParams, setSearchParams] = useSearchParams();
  const offeringId = searchParams.get("offering_id") ?? "";
  const typeParam = searchParams.get("type");
  const selectedType = isTemplateType(typeParam) ? typeParam : "";
  const [categories, setCategories] = useState<ConfigCategoryResponse[] | null>(null);
  const [templates, setTemplates] = useState<ConfigTemplateCatalogItem[] | null>(null);
  const [query, setQuery] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [previewingId, setPreviewingId] = useState<string | null>(null);
  const [previewDetail, setPreviewDetail] = useState<ConfigTemplateDetailResponse | null>(null);
  const [previewSubject, setPreviewSubject] = useState<string | null>(null);
  const [previewBody, setPreviewBody] = useState("");
  const [previewSamples, setPreviewSamples] = useState<Record<string, string>>({});

  useEffect(() => {
    let mounted = true;
    setCategories(null);
    setTemplates(null);
    setError(null);
    void Promise.all([fetchConfigCategories(), fetchConfigTemplates()]).then(([categoryRows, templateRows]) => {
      if (!mounted) return;
      setCategories(categoryRows);
      setTemplates(templateRows);
    }).catch((requestError: unknown) => {
      if (!mounted) return;
      setError(requestError instanceof Error ? requestError.message : "Templates could not be loaded.");
      setCategories([]);
      setTemplates([]);
    });
    return () => {
      mounted = false;
    };
  }, [focusRefreshKey]);

  const offerings = useMemo(() => offeringOptions(categories ?? []), [categories]);

  useEffect(() => {
    if (!offeringId || categories === null) return;
    if (offerings.some((offering) => offering.id === offeringId)) return;
    const next = new URLSearchParams(searchParams);
    next.delete("offering_id");
    setSearchParams(next, { replace: true });
  }, [categories, offeringId, offerings, searchParams, setSearchParams]);

  const updateFilter = (key: "offering_id" | "type", value: string) => {
    const next = new URLSearchParams(searchParams);
    if (value) next.set(key, value);
    else next.delete(key);
    setSearchParams(next, { replace: true });
  };

  const visibleTemplates = useMemo(() => (templates ?? []).filter((template) =>
    (!offeringId || template.offering_id === offeringId)
    && (!selectedType || template.template_type === selectedType)
    && templateMatches(template, query)
  ), [offeringId, query, selectedType, templates]);

  const openPreview = async (templateId: string) => {
    setPreviewingId(templateId);
    setError(null);
    try {
      const detail = await fetchTemplateDetail(templateId);
      const samples = sampleValues(detail);
      const rendered = await previewTemplate(templateId, samples);
      setPreviewDetail(detail);
      setPreviewSamples(samples);
      setPreviewSubject(rendered.subject);
      setPreviewBody(rendered.rendered_body);
    } catch (requestError: unknown) {
      setError(requestError instanceof Error ? requestError.message : "The template preview could not be rendered.");
    } finally {
      setPreviewingId(null);
    }
  };

  const updatePreviewSample = (key: string, value: string) => {
    if (!previewDetail) return;
    const next = { ...previewSamples, [key]: value };
    const rendered = renderEffectiveTemplate(previewDetail, next);
    setPreviewSamples(next);
    setPreviewSubject(rendered.subject);
    setPreviewBody(rendered.body);
  };

  const loading = categories === null || templates === null;
  const filterContext = searchParams.toString();

  return (
    <section className={styles.page}>
      <header className={styles.pageHeader}>
        <div>
          <h1>Templates</h1>
          <p>Manage and customize templates for your workspace.</p>
        </div>
      </header>

      <div className={styles.catalogPanel}>
        <div className={styles.toolbar}>
          <label className={styles.searchField}>
            <Search size={16} aria-hidden="true" />
            <span className={styles.srOnly}>Search templates</span>
            <input
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Search templates"
            />
          </label>

          <label className={styles.filterField}>
            <span className={styles.srOnly}>Format</span>
            <select
              aria-label="Format"
              value={selectedType}
              onChange={(event) => updateFilter("type", event.target.value)}
            >
              <option value="">All formats</option>
              {formatOptions.map((type) => (
                <option key={type} value={type}>{typeLabels[type]}</option>
              ))}
            </select>
          </label>

          <label className={styles.filterField}>
            <span className={styles.srOnly}>Offering</span>
            <select
              aria-label="Offering"
              value={offeringId}
              disabled={categories === null}
              onChange={(event) => updateFilter("offering_id", event.target.value)}
            >
              <option value="">All offerings</option>
              {offerings.map((offering) => (
                <option key={offering.id} value={offering.id}>{offering.name}</option>
              ))}
            </select>
          </label>

          <span className={styles.resultCount} aria-live="polite">
            {loading ? "Loading…" : `${visibleTemplates.length} ${visibleTemplates.length === 1 ? "template" : "templates"}`}
          </span>
        </div>

        {error && <div className={styles.alertWrap}><Alert tone="error" title="Templates unavailable">{error}</Alert></div>}

        {loading ? (
          <div className={styles.loadingState} role="status">Loading templates&hellip;</div>
        ) : categories.length === 0 ? (
          <div className={styles.emptyState}>
            <FileStack size={28} aria-hidden="true" />
            <h2>No licensed templates available</h2>
            <p>Your workspace has no active offerings with configuration templates.</p>
          </div>
        ) : visibleTemplates.length === 0 ? (
          <div className={styles.emptyState}>
            <FileStack size={28} aria-hidden="true" />
            <h2>No templates match these filters</h2>
            <p>Try a different search, format, or offering.</p>
          </div>
        ) : (
          <div className={styles.tableWrap}>
            <table>
              <thead>
                <tr>
                  <th>Template</th>
                  <th>Template type</th>
                  <th>Offering</th>
                  <th>Source</th>
                  <th>Preview</th>
                  <th>Edit</th>
                  <th>Created at</th>
                </tr>
              </thead>
              <tbody>
                {visibleTemplates.map((template) => {
                  const previewing = previewingId === template.template_id;
                  return (
                    <tr key={template.template_id}>
                      <td>
                        <div className={styles.templateIdentity}>
                          <span>
                            <strong>{template.display_name}</strong>
                            {!template.is_active && <em>Inactive</em>}
                          </span>
                          <small>{template.code}</small>
                        </div>
                      </td>
                      <td>
                        <span className={`${styles.typeBadge} ${styles[`type${template.template_type}`]}`}>
                          {typeLabels[template.template_type]}
                        </span>
                      </td>
                      <td>
                        <div className={styles.offeringCell}>
                          <span>{template.offering_name}</span>
                          <small>{template.offering_code}</small>
                        </div>
                      </td>
                      <td>
                        <span className={`${styles.sourceBadge} ${template.is_customized ? styles.customized : styles.platformDefault}`}>
                          {template.is_customized ? "Customized" : "Platform default"}
                        </span>
                      </td>
                      <td>
                        <button
                          type="button"
                          className={styles.rowAction}
                          disabled={previewingId !== null}
                          aria-label={`Preview ${template.display_name}`}
                          onClick={() => { void openPreview(template.template_id); }}
                        >
                          <Eye size={14} aria-hidden="true" />
                          {previewing ? "Loading…" : "Preview"}
                        </button>
                      </td>
                      <td>
                        <Link
                          className={styles.rowAction}
                          aria-label={`Edit ${template.display_name}`}
                          to={appPath(`/app/configurations/templates/${template.template_id}${filterContext ? `?${filterContext}` : ""}`)}
                        >
                          <Pencil size={14} aria-hidden="true" />
                          Edit
                        </Link>
                      </td>
                      <td className={styles.dateCell}>{formatCreatedAt(template.created_at)}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>

      <TemplatePreviewModal
        isOpen={previewDetail !== null}
        onClose={() => setPreviewDetail(null)}
        title={previewDetail?.display_name ?? "Template"}
        subject={previewSubject}
        body={previewBody}
        sampleData={previewSamples}
        onSampleDataChange={updatePreviewSample}
      />
    </section>
  );
};
