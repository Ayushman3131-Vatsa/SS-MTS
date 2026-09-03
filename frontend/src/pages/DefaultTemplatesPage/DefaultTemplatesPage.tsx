import { Eye, FileStack, Pencil, Plus, Search } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";

import { defaultTemplatesApi } from "../../features/default-template-management/api/default-templates-api";
import {
  DEFAULT_TEMPLATE_TYPES,
  type DefaultTemplateDetail,
  type DefaultTemplateListItem,
  type DefaultTemplateType,
} from "../../features/default-template-management/model/default-templates";
import { offeringsApi } from "../../features/offering-management/api/offerings-api";
import type { OfferingCatalogItem } from "../../features/offering-management/model/offerings";
import { canModifyPage } from "../../entities/session/model/page-access";
import { useOptionalSession } from "../../entities/session/model/session-context";
import { TemplatePreviewModal } from "../../features/configurations/ui/TemplatePreviewModal";
import { Alert } from "../../shared/ui/Alert/Alert";
import styles from "./DefaultTemplatesPage.module.css";

const typeLabels: Record<DefaultTemplateType, string> = {
  EMAIL: "Email",
  NOTIFICATION: "Notification",
  LETTER: "Letter",
  OTHER: "Other",
};

const formatOptions: DefaultTemplateType[] = [
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

const formatCreatedAt = (value: string) => {
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? "—" : dateFormatter.format(date);
};

const renderSavedTemplate = (
  template: DefaultTemplateDetail,
  sampleData: Record<string, string>,
) => {
  let subject = template.subject;
  let body = template.body;
  template.placeholders.forEach((placeholder) => {
    const value = sampleData[placeholder.key] ?? placeholder.sample_value;
    const token = `{{${placeholder.key}}}`;
    subject = subject?.split(token).join(value) ?? null;
    body = body.split(token).join(value);
  });
  return { subject, body };
};

export const DefaultTemplatesPage = () => {
  const principal = useOptionalSession()?.principal;
  const canModify = canModifyPage(principal, "/platform/default-templates");
  const [searchParams, setSearchParams] = useSearchParams();
  const offeringId = searchParams.get("offering_id") ?? "";
  const typeParam = searchParams.get("type");
  const selectedType = isTemplateType(typeParam) ? typeParam : "";
  const [offerings, setOfferings] = useState<OfferingCatalogItem[] | null>(null);
  const [templates, setTemplates] = useState<DefaultTemplateListItem[] | null>(null);
  const [templateQuery, setTemplateQuery] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [previewingId, setPreviewingId] = useState<string | null>(null);
  const [previewTemplate, setPreviewTemplate] = useState<DefaultTemplateDetail | null>(null);
  const [previewSubject, setPreviewSubject] = useState<string | null>(null);
  const [previewBody, setPreviewBody] = useState("");
  const [sampleData, setSampleData] = useState<Record<string, string>>({});

  useEffect(() => {
    const controller = new AbortController();
    void offeringsApi.list(controller.signal).then((result) => {
      setOfferings([...result].sort(
        (left, right) => left.sort_order - right.sort_order || left.display_name.localeCompare(right.display_name),
      ));
    }).catch((requestError: unknown) => {
      if (requestError instanceof DOMException && requestError.name === "AbortError") return;
      setError(requestError instanceof Error ? requestError.message : "Offerings could not be loaded.");
      setOfferings([]);
    });
    return () => controller.abort();
  }, []);

  useEffect(() => {
    if (!offeringId || offerings === null) return;
    if (offerings.some((offering) => offering.offering_id === offeringId)) return;
    const next = new URLSearchParams(searchParams);
    next.delete("offering_id");
    setSearchParams(next, { replace: true });
  }, [offeringId, offerings, searchParams, setSearchParams]);

  useEffect(() => {
    const controller = new AbortController();
    setTemplates(null);
    setError(null);
    void defaultTemplatesApi.list({
      offeringId: offeringId || undefined,
      signal: controller.signal,
    }).then(setTemplates).catch((requestError: unknown) => {
      if (requestError instanceof DOMException && requestError.name === "AbortError") return;
      setError(requestError instanceof Error ? requestError.message : "Default templates could not be loaded.");
      setTemplates([]);
    });
    return () => controller.abort();
  }, [offeringId]);

  const updateFilter = (key: "offering_id" | "type", value: string) => {
    const next = new URLSearchParams(searchParams);
    if (value) next.set(key, value);
    else next.delete(key);
    setSearchParams(next, { replace: true });
  };

  const visibleTemplates = useMemo(() => (templates ?? []).filter((template) =>
    (!selectedType || template.type === selectedType) && templateMatches(template, templateQuery)
  ), [selectedType, templateQuery, templates]);

  const offeringById = useMemo(
    () => new Map((offerings ?? []).map((offering) => [offering.offering_id, offering])),
    [offerings],
  );

  const createParams = new URLSearchParams();
  if (offeringId) createParams.set("offering_id", offeringId);
  if (selectedType) createParams.set("type", selectedType);
  const createSearch = createParams.size > 0 ? `?${createParams.toString()}` : "";

  const openPreview = async (templateId: string) => {
    setPreviewingId(templateId);
    setError(null);
    try {
      const detail = await defaultTemplatesApi.get(templateId);
      const samples = Object.fromEntries(
        detail.placeholders.map((placeholder) => [placeholder.key, placeholder.sample_value]),
      );
      const preview = await defaultTemplatesApi.preview({
        subject: detail.subject,
        body: detail.body,
        placeholders: detail.placeholders,
        sample_data: samples,
      });
      setPreviewTemplate(detail);
      setSampleData(samples);
      setPreviewSubject(preview.subject);
      setPreviewBody(preview.rendered_body);
    } catch (requestError: unknown) {
      setError(requestError instanceof Error ? requestError.message : "The template preview could not be rendered.");
    } finally {
      setPreviewingId(null);
    }
  };

  const updatePreviewSample = (key: string, value: string) => {
    if (!previewTemplate) return;
    const next = { ...sampleData, [key]: value };
    const rendered = renderSavedTemplate(previewTemplate, next);
    setSampleData(next);
    setPreviewSubject(rendered.subject);
    setPreviewBody(rendered.body);
  };

  return (
    <section className={styles.page}>
      <header className={styles.pageHeader}>
        <div>
          <h1>Templates</h1>
          <p>Manage templates</p>
        </div>
        {canModify && (
          <Link className={styles.createLink} to={`/platform/default-templates/new${createSearch}`}>
            <Plus size={16} aria-hidden="true" />
            New default template
          </Link>
        )}
      </header>

      <div className={styles.catalogPanel}>
        <div className={styles.toolbar}>
          <label className={styles.searchField}>
            <Search size={16} aria-hidden="true" />
            <span className={styles.srOnly}>Search templates</span>
            <input
              value={templateQuery}
              onChange={(event) => setTemplateQuery(event.target.value)}
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
              disabled={offerings === null}
              onChange={(event) => updateFilter("offering_id", event.target.value)}
            >
              <option value="">All offerings</option>
              {(offerings ?? []).map((offering) => (
                <option key={offering.offering_id} value={offering.offering_id}>
                  {offering.display_name}{offering.status === "INACTIVE" ? " (Inactive)" : ""}
                </option>
              ))}
            </select>
          </label>

          <span className={styles.resultCount} aria-live="polite">
            {templates === null ? "Loading…" : `${visibleTemplates.length} ${visibleTemplates.length === 1 ? "template" : "templates"}`}
          </span>
        </div>

        {error && <div className={styles.alertWrap}><Alert tone="error" title="Templates unavailable">{error}</Alert></div>}

        {templates === null ? (
          <div className={styles.loadingState} role="status">Loading default templates&hellip;</div>
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
                  <th>Default template</th>
                  <th>Template type</th>
                  <th>Offering</th>
                  <th>Preview</th>
                  <th>Edit</th>
                  <th>Created at</th>
                </tr>
              </thead>
              <tbody>
                {visibleTemplates.map((template) => {
                  const offering = offeringById.get(template.offering_id);
                  const previewing = previewingId === template.template_id;
                  return (
                    <tr key={template.template_id}>
                      <td>
                        <div className={styles.templateIdentity}>
                          <span>
                            <strong>{template.name}</strong>
                            {!template.is_active && <em>Inactive</em>}
                          </span>
                          <small>{template.code}</small>
                        </div>
                      </td>
                      <td>
                        <span className={`${styles.typeBadge} ${styles[`type${template.type}`]}`}>
                          {typeLabels[template.type]}
                        </span>
                      </td>
                      <td>
                        <div className={styles.offeringCell}>
                          <span>{template.offering_name}</span>
                          <small>{template.offering_code}{offering?.status === "INACTIVE" ? " · Inactive" : ""}</small>
                        </div>
                      </td>
                      <td>
                        <button
                          type="button"
                          className={styles.rowAction}
                          disabled={previewingId !== null}
                          aria-label={`Preview ${template.name}`}
                          onClick={() => { void openPreview(template.template_id); }}
                        >
                          <Eye size={14} aria-hidden="true" />
                          {previewing ? "Loading…" : "Preview"}
                        </button>
                      </td>
                      <td>
                        <Link
                          className={styles.rowAction}
                          aria-label={`Edit ${template.name}`}
                          to={`/platform/default-templates/${template.template_id}?offering_id=${template.offering_id}&type=${template.type}`}
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
        isOpen={previewTemplate !== null}
        onClose={() => setPreviewTemplate(null)}
        title={previewTemplate?.name ?? "Template"}
        subject={previewSubject}
        body={previewBody}
        sampleData={sampleData}
        onSampleDataChange={updatePreviewSample}
      />
    </section>
  );
};
