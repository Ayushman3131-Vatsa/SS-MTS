import {
  ArrowLeft,
  CheckCircle2,
  Eye,
  FileText,
  LockKeyhole,
  Plus,
  Save,
  Tag,
  Trash2,
  Users,
} from "lucide-react";
import { useEffect, useMemo, useRef, useState, type FormEvent } from "react";
import {
  Link,
  useBlocker,
  useNavigate,
  useParams,
  useSearchParams,
} from "react-router-dom";

import { defaultTemplatesApi } from "../../features/default-template-management/api/default-templates-api";
import {
  DEFAULT_TEMPLATE_TYPES,
  type DefaultTemplateCreatePayload,
  type DefaultTemplateDetail,
  type DefaultTemplatePlaceholder,
  type DefaultTemplateType,
  type DefaultTemplateUpdatePayload,
} from "../../features/default-template-management/model/default-templates";
import { offeringsApi } from "../../features/offering-management/api/offerings-api";
import type { OfferingCatalogItem } from "../../features/offering-management/model/offerings";
import { canModifyPage } from "../../entities/session/model/page-access";
import { useOptionalSession } from "../../entities/session/model/session-context";
import { TemplatePreviewModal } from "../../features/configurations/ui/TemplatePreviewModal";
import { ApiError } from "../../shared/api/errors";
import { Alert } from "../../shared/ui/Alert/Alert";
import { Button } from "../../shared/ui/Button/Button";
import { ConfirmDialog } from "../../shared/ui/ConfirmDialog/ConfirmDialog";
import styles from "./DefaultTemplateEditorPage.module.css";

interface EditorValues {
  offering_id: string;
  code: string;
  name: string;
  description: string;
  type: DefaultTemplateType;
  subject: string;
  body: string;
  placeholders: DefaultTemplatePlaceholder[];
  sort_order: number;
}

const typeLabels: Record<DefaultTemplateType, string> = {
  EMAIL: "Email",
  LETTER: "Letter",
  NOTIFICATION: "Notification",
  OTHER: "Other",
};

const isTemplateType = (value: string | null): value is DefaultTemplateType =>
  DEFAULT_TEMPLATE_TYPES.some((type) => type === value);

const blankEditor = (offeringId = "", type: DefaultTemplateType = "EMAIL"): EditorValues => ({
  offering_id: offeringId,
  code: "",
  name: "",
  description: "",
  type,
  subject: "",
  body: "",
  placeholders: [],
  sort_order: 0,
});

const editorFromDetail = (detail: DefaultTemplateDetail): EditorValues => ({
  offering_id: detail.offering_id,
  code: detail.code,
  name: detail.name,
  description: detail.description,
  type: detail.type,
  subject: detail.subject ?? "",
  body: detail.body,
  placeholders: detail.placeholders,
  sort_order: detail.sort_order,
});

const serializeEditor = (editor: EditorValues) => JSON.stringify(editor);

const toCodePart = (value: string) => value
  .normalize("NFKD")
  .replace(/[\u0300-\u036f]/g, "")
  .toLowerCase()
  .trim()
  .replace(/[^a-z0-9]+/g, "_")
  .replace(/^_+|_+$/g, "");

const toTemplateCode = (offeringCode: string, name: string) => {
  const prefix = toCodePart(offeringCode);
  const slug = toCodePart(name);
  if (!prefix || !slug) return "";
  return `${prefix}_${slug}`.slice(0, 100).replace(/_+$/g, "");
};

const normalizeSubject = (subject: string) => {
  const normalized = subject.trim();
  return normalized || null;
};

const serializeComparableEditor = (editor: EditorValues) => JSON.stringify({
  ...editor,
  subject: normalizeSubject(editor.subject),
});

const validateEditor = (editor: EditorValues): string | null => {
  if (!editor.offering_id) return "Choose the offering that will own this default template.";
  if (!/^[a-z][a-z0-9_]{0,99}$/.test(editor.code)) {
    return "Template code must use lower_snake_case and start with a letter.";
  }
  if (!editor.name.trim()) return "Enter a template name.";
  if (!editor.body.trim()) return "Enter the template body.";

  const declaredKeys = editor.placeholders.map((placeholder) => placeholder.key);
  const uniqueKeys = new Set(declaredKeys);
  if (uniqueKeys.size !== declaredKeys.length) return "Every placeholder key must be unique.";
  for (const placeholder of editor.placeholders) {
    if (placeholder.key.length > 64 || !/^[a-z][a-z0-9_]*$/.test(placeholder.key)) {
      return "Placeholder keys must use lower_snake_case and start with a letter.";
    }
    if (!placeholder.label.trim()) return `Add a label for {{${placeholder.key}}}.`;
  }

  const content = `${editor.subject}\n${editor.body}`;
  if (content.includes("{{{") || content.includes("}}}")) {
    return "Every template token must use the exact {{lower_snake_case}} format.";
  }
  const usedKeys = new Set<string>();
  const tokenPattern = /\{\{([a-z][a-z0-9_]*)\}\}/g;
  for (const match of content.matchAll(tokenPattern)) {
    usedKeys.add(match[1]);
  }
  const withoutValidTokens = content.replace(tokenPattern, "");
  if (withoutValidTokens.includes("{{") || withoutValidTokens.includes("}}")) {
    return "Every template token must use the exact {{lower_snake_case}} format.";
  }
  const undeclared = [...usedKeys].filter((key) => !uniqueKeys.has(key));
  if (undeclared.length > 0) return `Declare the {{${undeclared[0]}}} placeholder before saving.`;
  const unused = editor.placeholders
    .filter((placeholder) => placeholder.required && !usedKeys.has(placeholder.key))
    .map((placeholder) => placeholder.key);
  if (unused.length > 0) return `Insert {{${unused[0]}}} into the subject or body, or remove it.`;

  return null;
};

const renderDraft = (
  editor: EditorValues,
  sampleData: Record<string, string>,
) => {
  let subject = editor.subject;
  let body = editor.body;
  editor.placeholders.forEach((placeholder) => {
    const token = `{{${placeholder.key}}}`;
    const value = sampleData[placeholder.key] ?? placeholder.sample_value;
    subject = subject.split(token).join(value);
    body = body.split(token).join(value);
  });
  return { subject: normalizeSubject(subject), body };
};

export const DefaultTemplateEditorPage = () => {
  const principal = useOptionalSession()?.principal;
  const canModify = canModifyPage(principal, "/platform/default-templates");
  const { templateId } = useParams<{ templateId: string }>();
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const isEditing = Boolean(templateId);
  const [form, setForm] = useState<EditorValues>(() => {
    const requestedType = searchParams.get("type");
    return blankEditor(
      searchParams.get("offering_id") ?? "",
      isTemplateType(requestedType) ? requestedType : "EMAIL",
    );
  });
  const [baseline, setBaseline] = useState<string | null>(null);
  const [detail, setDetail] = useState<DefaultTemplateDetail | null>(null);
  const [offerings, setOfferings] = useState<OfferingCatalogItem[] | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [previewing, setPreviewing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [stale, setStale] = useState(false);
  const [reloadKey, setReloadKey] = useState(0);
  const [codeWasEdited, setCodeWasEdited] = useState(isEditing);
  const [previewOpen, setPreviewOpen] = useState(false);
  const [sampleData, setSampleData] = useState<Record<string, string>>({});
  const [previewSubject, setPreviewSubject] = useState<string | null>(null);
  const [previewBody, setPreviewBody] = useState("");
  const formRef = useRef<HTMLFormElement>(null);
  const subjectRef = useRef<HTMLInputElement>(null);
  const bodyRef = useRef<HTMLTextAreaElement>(null);
  const insertionTargetRef = useRef<"subject" | "body">("body");
  const allowNavigationRef = useRef(false);

  useEffect(() => {
    const controller = new AbortController();
    void offeringsApi.list(controller.signal).then(setOfferings).catch((requestError: unknown) => {
      if (requestError instanceof DOMException && requestError.name === "AbortError") return;
      setOfferings([]);
      if (!templateId) setError(requestError instanceof Error ? requestError.message : "Offerings could not be loaded.");
    });
    return () => controller.abort();
  }, [templateId]);

  useEffect(() => {
    if (templateId || offerings === null || baseline !== null) return;
    setForm((current) => {
      const requestedExists = offerings.some((offering) => offering.offering_id === current.offering_id);
      const next = {
        ...current,
        offering_id: requestedExists ? current.offering_id : offerings[0]?.offering_id ?? current.offering_id,
      };
      setBaseline(serializeEditor(next));
      return next;
    });
    setLoading(false);
  }, [baseline, offerings, templateId]);

  useEffect(() => {
    if (!templateId) return;
    const controller = new AbortController();
    setLoading(true);
    setError(null);
    setStale(false);
    void defaultTemplatesApi.get(templateId, controller.signal).then((result) => {
      const next = editorFromDetail(result);
      setDetail(result);
      setForm(next);
      setBaseline(serializeEditor(next));
      setCodeWasEdited(true);
      allowNavigationRef.current = false;
    }).catch((requestError: unknown) => {
      if (requestError instanceof DOMException && requestError.name === "AbortError") return;
      setDetail(null);
      setError(requestError instanceof Error ? requestError.message : "The default template could not be loaded.");
    }).finally(() => {
      if (!controller.signal.aborted) setLoading(false);
    });
    return () => controller.abort();
  }, [reloadKey, templateId]);

  const dirty = baseline !== null
    && serializeComparableEditor(form) !== serializeComparableEditor(JSON.parse(baseline) as EditorValues);
  const blocker = useBlocker(({ currentLocation, nextLocation }) =>
    dirty
    && !allowNavigationRef.current
    && `${currentLocation.pathname}${currentLocation.search}` !== `${nextLocation.pathname}${nextLocation.search}`
  );

  useEffect(() => {
    if (!dirty) return;
    const protectDraft = (event: BeforeUnloadEvent) => {
      event.preventDefault();
      event.returnValue = "";
    };
    window.addEventListener("beforeunload", protectDraft);
    return () => window.removeEventListener("beforeunload", protectDraft);
  }, [dirty]);

  useEffect(() => {
    const saveShortcut = (event: KeyboardEvent) => {
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "s") {
        event.preventDefault();
        if (dirty && !saving) formRef.current?.requestSubmit();
      }
    };
    document.addEventListener("keydown", saveShortcut);
    return () => document.removeEventListener("keydown", saveShortcut);
  }, [dirty, saving]);

  const selectedOffering = offerings?.find((offering) => offering.offering_id === form.offering_id);
  const sortedOfferings = useMemo(() => [...(offerings ?? [])].sort(
    (left, right) => left.sort_order - right.sort_order || left.display_name.localeCompare(right.display_name),
  ), [offerings]);
  const catalogParams = new URLSearchParams();
  if (form.offering_id) catalogParams.set("offering_id", form.offering_id);
  catalogParams.set("type", form.type);
  const catalogUrl = `/platform/default-templates?${catalogParams.toString()}`;

  const updateForm = <K extends keyof EditorValues>(field: K, value: EditorValues[K]) => {
    setNotice(null);
    setForm((current) => ({ ...current, [field]: value }));
  };

  const updateName = (name: string) => {
    setNotice(null);
    setForm((current) => ({
      ...current,
      name,
      code: !isEditing && !codeWasEdited
        ? toTemplateCode(offerings?.find((offering) => offering.offering_id === current.offering_id)?.code ?? "", name)
        : current.code,
    }));
  };

  const updateOffering = (offeringId: string) => {
    const offeringCode = offerings?.find((offering) => offering.offering_id === offeringId)?.code ?? "";
    setNotice(null);
    setForm((current) => ({
      ...current,
      offering_id: offeringId,
      code: !codeWasEdited ? toTemplateCode(offeringCode, current.name) : current.code,
    }));
  };

  const updatePlaceholder = (
    index: number,
    field: keyof DefaultTemplatePlaceholder,
    value: string | boolean,
  ) => {
    setNotice(null);
    setForm((current) => ({
      ...current,
      placeholders: current.placeholders.map((placeholder, placeholderIndex) =>
        placeholderIndex === index ? { ...placeholder, [field]: value } : placeholder
      ),
    }));
  };

  const addPlaceholder = () => {
    updateForm("placeholders", [
      ...form.placeholders,
      { key: "", label: "", sample_value: "", required: false },
    ]);
  };

  const removePlaceholder = (index: number) => {
    updateForm("placeholders", form.placeholders.filter((_, placeholderIndex) => placeholderIndex !== index));
  };

  const insertPlaceholder = (key: string) => {
    if (!key) return;
    const target = insertionTargetRef.current;
    const element = target === "subject" ? subjectRef.current : bodyRef.current;
    const currentText = form[target];
    const start = element?.selectionStart ?? currentText.length;
    const end = element?.selectionEnd ?? start;
    const token = `{{${key}}}`;
    const nextText = `${currentText.slice(0, start)}${token}${currentText.slice(end)}`;
    updateForm(target, nextText);
    window.requestAnimationFrame(() => {
      const nextElement = target === "subject" ? subjectRef.current : bodyRef.current;
      nextElement?.focus();
      nextElement?.setSelectionRange(start + token.length, start + token.length);
    });
  };

  const saveTemplate = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setStale(false);
    const validationError = validateEditor(form);
    if (validationError) {
      setError(validationError);
      return;
    }
    setSaving(true);
    setError(null);
    setNotice(null);
    setStale(false);
    try {
      let result: DefaultTemplateDetail;
      if (templateId && detail && baseline) {
        const original = JSON.parse(baseline) as EditorValues;
        const payload: DefaultTemplateUpdatePayload = { expected_version: detail.version };
        if (form.name !== original.name) payload.name = form.name.trim();
        if (form.description !== original.description) payload.description = form.description.trim();
        if (normalizeSubject(form.subject) !== normalizeSubject(original.subject)) payload.subject = normalizeSubject(form.subject);
        if (form.body !== original.body) payload.body = form.body;
        if (JSON.stringify(form.placeholders) !== JSON.stringify(original.placeholders)) payload.placeholders = form.placeholders;
        if (form.sort_order !== original.sort_order) payload.sort_order = form.sort_order;
        if (Object.keys(payload).length === 1) {
          const normalized = { ...form, subject: normalizeSubject(form.subject) ?? "" };
          setForm(normalized);
          setBaseline(serializeEditor(normalized));
          setNotice("There were no publishable changes.");
          return;
        }
        result = await defaultTemplatesApi.update(templateId, payload);
      } else {
        const payload: DefaultTemplateCreatePayload = {
          offering_id: form.offering_id,
          code: form.code,
          name: form.name.trim(),
          description: form.description.trim(),
          type: form.type,
          subject: normalizeSubject(form.subject),
          body: form.body,
          placeholders: form.placeholders,
          sort_order: form.sort_order,
        };
        result = await defaultTemplatesApi.create(payload);
      }

      const next = editorFromDetail(result);
      setDetail(result);
      setForm(next);
      setBaseline(serializeEditor(next));
      setNotice(templateId ? "Default template updated." : "Default template created and published.");
      if (!templateId) {
        allowNavigationRef.current = true;
        const nextContext = new URLSearchParams({
          offering_id: result.offering_id,
          type: result.type,
        });
        navigate(`/platform/default-templates/${result.template_id}?${nextContext.toString()}`, { replace: true });
      }
    } catch (requestError: unknown) {
      if (requestError instanceof ApiError && requestError.code === "DEFAULT_TEMPLATE_STALE") {
        setStale(true);
        setError("A newer version was saved by another administrator. Reload it before applying your changes.");
      } else {
        setError(requestError instanceof Error ? requestError.message : "The default template could not be saved.");
      }
    } finally {
      setSaving(false);
    }
  };

  const openPreview = async () => {
    setStale(false);
    const validationError = validateEditor(form);
    if (validationError) {
      setError(validationError);
      return;
    }
    const samples = Object.fromEntries(form.placeholders.map((placeholder) => [
      placeholder.key,
      sampleData[placeholder.key] ?? placeholder.sample_value,
    ]));
    setSampleData(samples);
    setPreviewing(true);
    setError(null);
    try {
      const preview = await defaultTemplatesApi.preview({
        subject: normalizeSubject(form.subject),
        body: form.body,
        placeholders: form.placeholders,
        sample_data: samples,
      });
      setPreviewSubject(preview.subject);
      setPreviewBody(preview.rendered_body);
      setPreviewOpen(true);
    } catch (requestError: unknown) {
      setError(requestError instanceof Error ? requestError.message : "The draft preview could not be rendered.");
    } finally {
      setPreviewing(false);
    }
  };

  const updateSample = (key: string, value: string) => {
    const next = { ...sampleData, [key]: value };
    const rendered = renderDraft(form, next);
    setSampleData(next);
    setPreviewSubject(rendered.subject);
    setPreviewBody(rendered.body);
  };

  if (loading) {
    return <div className={styles.loadingState} role="status">Loading template editor&hellip;</div>;
  }

  if (isEditing && !detail) {
    return (
      <div className={styles.loadFailure}>
        <Alert tone="error" title="Template unavailable">{error ?? "This default template could not be loaded."}</Alert>
        <Link to={catalogUrl}><ArrowLeft size={16} aria-hidden="true" /> Back to default templates</Link>
      </div>
    );
  }

  return (
    <div className={styles.page}>
      <header className={styles.topbar}>
        <div className={styles.breadcrumb}>
          <Link to={catalogUrl}><ArrowLeft size={17} aria-hidden="true" /> Default templates</Link>
          <span aria-hidden="true">/</span>
          <strong>{isEditing ? form.name : "New template"}</strong>
        </div>
        <div className={styles.topActions}>
          <span className={dirty ? styles.dirtyStatus : (isEditing ? styles.savedStatus : styles.draftStatus)}>
            {isEditing ? (dirty ? "Unsaved changes" : "All changes saved") : (dirty ? "Unsaved draft" : "New draft")}
          </span>
          <Button type="button" variant="secondary" disabled={saving} loading={previewing} loadingLabel="Rendering preview&hellip;" onClick={() => { void openPreview(); }}>
            <Eye size={16} aria-hidden="true" /> Preview draft
          </Button>
          <Button type="button" loading={saving} loadingLabel="Saving&hellip;" disabled={!dirty || !canModify} onClick={() => formRef.current?.requestSubmit()}>
            <Save size={16} aria-hidden="true" /> {isEditing ? "Publish changes" : "Create & publish"}
          </Button>
        </div>
      </header>

      <div className={styles.content}>
        <div className={styles.titleBlock}>
          <div>
            <p>{isEditing ? `VERSION ${detail?.version ?? ""}` : "NEW PLATFORM DEFAULT"}</p>
            <h1>{isEditing ? form.name : "Create default template"}</h1>
            <span>{isEditing ? "Changes flow to tenants that still inherit this default." : "New defaults are published immediately and become available to eligible tenants."}</span>
          </div>
          {!isEditing ? (
            <span className={styles.unpublishedBadge}><FileText size={14} aria-hidden="true" /> Not published</span>
          ) : (
            <span className={detail?.is_active === false ? styles.inactiveBadge : styles.publishedBadge}>
              {detail?.is_active === false ? <LockKeyhole size={14} aria-hidden="true" /> : <CheckCircle2 size={14} aria-hidden="true" />}
              {detail?.is_active === false ? "Inactive" : "Published"}
            </span>
          )}
        </div>

        {!canModify && (
          <Alert tone="info" title="Read-only mode">
            You have view-only access to default templates. Publishing changes is disabled.
          </Alert>
        )}

        {notice && <Alert tone="success" title="Saved">{notice}</Alert>}
        {error && (
          <Alert tone="error" title={stale ? "Version conflict" : "Action unavailable"}>
            {error}
            {stale && <Button type="button" variant="ghost" onClick={() => setReloadKey((value) => value + 1)}>Reload and discard draft</Button>}
          </Alert>
        )}

        {isEditing && detail && (
          <section className={styles.impactBanner} aria-label="Tenant impact">
            <div><Users size={19} aria-hidden="true" /><span><strong>{detail.inheriting_tenant_count}</strong> tenants inherit this default</span></div>
            <div><Users size={19} aria-hidden="true" /><span><strong>{detail.customized_tenant_count}</strong> tenants have customizations</span></div>
            <p>Saving updates inheriting tenants. Customized tenant versions remain unchanged.</p>
          </section>
        )}

        <form ref={formRef} className={styles.form} aria-busy={saving} onSubmit={(event) => { void saveTemplate(event); }}>
          <fieldset className={styles.formFields} disabled={saving}>
          <section className={styles.card} aria-labelledby="template-identity-heading">
            <div className={styles.sectionHeading}>
              <span><FileText size={17} aria-hidden="true" /></span>
              <div><h2 id="template-identity-heading">Template identity</h2><p>Ownership and stable identifiers used by product workflows.</p></div>
            </div>
            <div className={styles.identityGrid}>
              <label>
                <span>Offering</span>
                {isEditing ? (
                  <span className={styles.lockedField}><LockKeyhole size={14} aria-hidden="true" /><input aria-label="Offering" value={detail?.offering_name ?? selectedOffering?.display_name ?? ""} disabled /></span>
                ) : (
                  <select aria-label="Offering" required value={form.offering_id} onChange={(event) => updateOffering(event.target.value)}>
                    <option value="" disabled>Choose an offering</option>
                    {sortedOfferings.map((offering) => <option key={offering.offering_id} value={offering.offering_id}>{offering.display_name}{offering.status === "INACTIVE" ? " (Inactive)" : ""}</option>)}
                  </select>
                )}
                {!isEditing && selectedOffering?.status === "INACTIVE" && <small>This future or inactive offering can still receive platform defaults.</small>}
              </label>
              {isEditing && (
                <label>
                  <span>Configuration category</span>
                  <span className={styles.lockedField}><LockKeyhole size={14} aria-hidden="true" /><input aria-label="Configuration category" value={detail?.category_name ?? ""} disabled /></span>
                </label>
              )}
              <label>
                <span>Template type</span>
                <span className={isEditing ? styles.lockedField : undefined}>
                  {isEditing && <LockKeyhole size={14} aria-hidden="true" />}
                  <select aria-label="Template type" disabled={isEditing} value={form.type} onChange={(event) => updateForm("type", event.target.value as DefaultTemplateType)}>
                    {DEFAULT_TEMPLATE_TYPES.map((type) => <option key={type} value={type}>{typeLabels[type]}</option>)}
                  </select>
                </span>
                {!isEditing && <small>The server creates or reuses the matching category.</small>}
              </label>
              <label>
                <span>Template code</span>
                <span className={isEditing ? styles.lockedField : undefined}>
                  {isEditing && <LockKeyhole size={14} aria-hidden="true" />}
                  <input
                    aria-label="Template code"
                    required
                    disabled={isEditing}
                    maxLength={100}
                    value={form.code}
                    pattern="[a-z][a-z0-9_]{0,99}"
                    title="Lowercase letters, numbers, and underscores; start with a letter"
                    onChange={(event) => {
                      setCodeWasEdited(true);
                      updateForm("code", event.target.value.toLowerCase().replace(/[^a-z0-9_]/g, ""));
                    }}
                  />
                </span>
                {!isEditing && <small>Generated from the name until you edit it.</small>}
              </label>
              <label className={styles.nameField}>
                <span>Display name</span>
                <input aria-label="Display name" required maxLength={200} value={form.name} onChange={(event) => updateName(event.target.value)} />
              </label>
              <label className={styles.descriptionField}>
                <span>Description</span>
                <textarea maxLength={5000} rows={3} value={form.description} onChange={(event) => updateForm("description", event.target.value)} />
              </label>
              <label>
                <span>Display order</span>
                <input required type="number" min={0} step={1} value={form.sort_order} onChange={(event) => updateForm("sort_order", Number(event.target.value))} />
              </label>
            </div>
          </section>

          <section className={styles.card} aria-labelledby="template-content-heading">
            <div className={styles.sectionHeading}>
              <span><FileText size={17} aria-hidden="true" /></span>
              <div><h2 id="template-content-heading">Default content</h2><p>Write the subject and Markdown body tenants inherit.</p></div>
            </div>
            <div className={styles.contentFields}>
              <label>
                <span>Subject <small>Optional</small></span>
                <input
                  ref={subjectRef}
                  maxLength={500}
                  value={form.subject}
                  onFocus={() => { insertionTargetRef.current = "subject"; }}
                  onChange={(event) => updateForm("subject", event.target.value)}
                  placeholder="For example: Welcome to {{company_name}}"
                />
              </label>
              <label>
                <span>Template body <small>Markdown supported</small></span>
                <textarea
                  ref={bodyRef}
                  required
                  rows={18}
                  maxLength={50000}
                  value={form.body}
                  onFocus={() => { insertionTargetRef.current = "body"; }}
                  onChange={(event) => updateForm("body", event.target.value)}
                  placeholder="Write the platform default template&hellip;"
                />
              </label>
            </div>
          </section>

          <section className={styles.card} aria-labelledby="template-placeholders-heading">
            <div className={styles.placeholderHeading}>
              <div className={styles.sectionHeading}>
                <span><Tag size={17} aria-hidden="true" /></span>
                <div><h2 id="template-placeholders-heading">Placeholders</h2><p>Declare every token used in the subject or body.</p></div>
              </div>
              {!isEditing && <Button type="button" variant="secondary" disabled={form.placeholders.length >= 100} onClick={addPlaceholder}><Plus size={15} aria-hidden="true" /> Add placeholder</Button>}
            </div>

            {form.placeholders.length === 0 ? (
              <div className={styles.emptyPlaceholders}><Tag size={21} aria-hidden="true" /><p>No placeholders declared. Add one to insert dynamic sample data.</p></div>
            ) : (
              <div className={styles.placeholderList}>
                {form.placeholders.map((placeholder, index) => (
                  <div className={styles.placeholderRow} key={index}>
                    <label><span>Key</span><input aria-label="Key" required disabled={isEditing} maxLength={64} value={placeholder.key} pattern="[a-z][a-z0-9_]*" placeholder="employee_name" onChange={(event) => updatePlaceholder(index, "key", event.target.value.toLowerCase().replace(/[^a-z0-9_]/g, ""))} /></label>
                    <label><span>Label</span><input required maxLength={100} value={placeholder.label} placeholder="Employee name" onChange={(event) => updatePlaceholder(index, "label", event.target.value)} /></label>
                    <label><span>Sample value</span><input maxLength={1000} value={placeholder.sample_value} placeholder="Ada Lovelace" onChange={(event) => updatePlaceholder(index, "sample_value", event.target.value)} /></label>
                    <label className={styles.requiredToggle}><input type="checkbox" disabled={isEditing} checked={placeholder.required} onChange={(event) => updatePlaceholder(index, "required", event.target.checked)} /><span>Required value</span></label>
                    <div className={styles.placeholderActions}>
                      <Button type="button" variant="ghost" disabled={!placeholder.key} onClick={() => insertPlaceholder(placeholder.key)}>Insert {placeholder.key ? `{{${placeholder.key}}}` : "token"}</Button>
                      {!isEditing && <Button type="button" variant="ghost" aria-label={`Remove ${placeholder.key || `placeholder ${index + 1}`}`} onClick={() => removePlaceholder(index)}><Trash2 size={15} aria-hidden="true" /></Button>}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </section>

          <footer className={styles.formFooter}>
            <span>Tip: press <kbd>Ctrl</kbd>/<kbd>Cmd</kbd> + <kbd>S</kbd> to save.</span>
            <div>
              <Button type="button" variant="secondary" onClick={() => { void openPreview(); }} loading={previewing} loadingLabel="Rendering preview&hellip;"><Eye size={16} aria-hidden="true" /> Preview draft</Button>
              <Button type="submit" disabled={!dirty} loading={saving} loadingLabel="Saving&hellip;"><Save size={16} aria-hidden="true" /> {isEditing ? "Publish changes" : "Create & publish"}</Button>
            </div>
          </footer>
          </fieldset>
        </form>
      </div>

      <TemplatePreviewModal
        isOpen={previewOpen}
        onClose={() => setPreviewOpen(false)}
        title={form.name || "Draft template"}
        subject={previewSubject}
        body={previewBody}
        sampleData={sampleData}
        onSampleDataChange={updateSample}
      />

      <ConfirmDialog
        open={blocker.state === "blocked"}
        title="Discard unsaved changes?"
        description="Your default template draft has not been saved. Leaving this page will discard it."
        confirmLabel="Discard draft"
        destructive
        onCancel={() => blocker.reset?.()}
        onConfirm={() => blocker.proceed?.()}
      />
    </div>
  );
};
