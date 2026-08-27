import React, { useEffect, useRef, useState } from "react";
import { useParams, useNavigate, Link } from "react-router-dom";
import {
  ArrowLeft,
  Save,
  RotateCcw,
  Eye,
  Loader2,
  AlertCircle,
  Check,
  FileCode2,
  Tag,
  SlidersHorizontal,
  CheckCircle2,
} from "lucide-react";

import {
  fetchTemplateDetail,
  saveTemplateOverride,
  resetTemplateOverride,
  previewTemplate,
} from "../../features/configurations/api/configuration-api";
import type { ConfigTemplateDetailResponse } from "../../features/configurations/model/types";
import { TemplatePreviewModal } from "../../features/configurations/ui/TemplatePreviewModal";
import { useWindowFocusRefresh } from "../../shared/model/useWindowFocusRefresh";
import { useTenantAppPath } from "../../entities/session/model/routing";
import styles from "./ConfigTemplateEditorPage.module.css";

interface TemplateDraft {
  subject: string;
  body: string;
}

const toTemplateDraft = (data: ConfigTemplateDetailResponse): TemplateDraft => ({
  subject: data.subject ?? "",
  body: data.body,
});

const toSampleData = (data: ConfigTemplateDetailResponse): Record<string, string> =>
  Object.fromEntries(
    data.placeholders.map((placeholder) => [placeholder.key, placeholder.sample_value || ""]),
  );

export const ConfigTemplateEditorPage: React.FC = () => {
  const { templateId } = useParams<{ templateId: string }>();
  const navigate = useNavigate();
  const appPath = useTenantAppPath();
  const focusRefreshKey = useWindowFocusRefresh();

  const [template, setTemplate] = useState<ConfigTemplateDetailResponse | null>(null);
  const [subject, setSubject] = useState<string>("");
  const [body, setBody] = useState<string>("");
  const loadedTemplateIdRef = useRef<string | null>(null);
  const draftRef = useRef<TemplateDraft>({ subject: "", body: "" });
  const baselineRef = useRef<TemplateDraft>({ subject: "", body: "" });

  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [resetting, setResetting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  // Preview state
  const [isPreviewOpen, setIsPreviewOpen] = useState(false);
  const [sampleData, setSampleData] = useState<Record<string, string>>({});
  const [previewSubject, setPreviewSubject] = useState<string | null>(null);
  const [previewBody, setPreviewBody] = useState<string>("");

  // Confirmation dialog state
  const [isResetConfirmOpen, setIsResetConfirmOpen] = useState(false);

  useEffect(() => {
    if (!templateId) return;

    let isMounted = true;
    const isDifferentTemplate = loadedTemplateIdRef.current !== templateId;
    const loadTemplate = async () => {
      if (isDifferentTemplate) {
        setLoading(true);
        setTemplate(null);
      }
      setError(null);
      try {
        const data = await fetchTemplateDetail(templateId);
        if (isMounted) {
          const nextDraft = toTemplateDraft(data);
          const hasUnsavedDraft =
            draftRef.current.subject !== baselineRef.current.subject ||
            draftRef.current.body !== baselineRef.current.body;

          setTemplate(data);
          if (isDifferentTemplate || !hasUnsavedDraft) {
            setSubject(nextDraft.subject);
            setBody(nextDraft.body);
            setSampleData(toSampleData(data));
            draftRef.current = nextDraft;
          }
          baselineRef.current = nextDraft;
          loadedTemplateIdRef.current = templateId;
        }
      } catch (err) {
        if (isMounted) {
          setError(err instanceof Error ? err.message : "Failed to load template");
        }
      } finally {
        if (isMounted) setLoading(false);
      }
    };

    loadTemplate();
    return () => {
      isMounted = false;
    };
  }, [focusRefreshKey, templateId]);

  const handleInsertPlaceholder = (key: string) => {
    const token = `{{${key}}}`;
    setBody((previousBody) => {
      const nextBody = previousBody + token;
      draftRef.current = { ...draftRef.current, body: nextBody };
      return nextBody;
    });
  };

  const handleSave = async () => {
    if (!templateId) return;
    setSaving(true);
    setError(null);
    setSuccessMessage(null);

    try {
      const updated = await saveTemplateOverride(templateId, {
        subject: subject.trim() || null,
        body: body,
      });
      const savedDraft = toTemplateDraft(updated);
      setTemplate(updated);
      setSubject(savedDraft.subject);
      setBody(savedDraft.body);
      draftRef.current = savedDraft;
      baselineRef.current = savedDraft;
      setSuccessMessage("Customization saved successfully!");
      setTimeout(() => setSuccessMessage(null), 4000);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save template customization");
    } finally {
      setSaving(false);
    }
  };

  const handleReset = async () => {
    if (!templateId) return;
    setResetting(true);
    setError(null);
    setSuccessMessage(null);
    setIsResetConfirmOpen(false);

    try {
      const resetData = await resetTemplateOverride(templateId);
      const resetDraft = toTemplateDraft(resetData);
      setTemplate(resetData);
      setSubject(resetDraft.subject);
      setBody(resetDraft.body);
      setSampleData(toSampleData(resetData));
      draftRef.current = resetDraft;
      baselineRef.current = resetDraft;
      setSuccessMessage("Template reset to platform default.");
      setTimeout(() => setSuccessMessage(null), 4000);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to reset template");
    } finally {
      setResetting(false);
    }
  };

  const handleOpenPreview = async () => {
    if (!templateId) return;
    try {
      const res = await previewTemplate(templateId, sampleData);
      setPreviewSubject(res.subject);
      setPreviewBody(res.rendered_body);
      setIsPreviewOpen(true);
    } catch {
      // Fallback to client-side placeholder replacement preview if API call fails
      let clientSubject = subject;
      let clientBody = body;
      Object.entries(sampleData).forEach(([k, v]) => {
        const reg = new RegExp(`\\{\\{${k}\\}\\}`, "g");
        clientSubject = clientSubject.replace(reg, v);
        clientBody = clientBody.replace(reg, v);
      });
      setPreviewSubject(clientSubject);
      setPreviewBody(clientBody);
      setIsPreviewOpen(true);
    }
  };

  const handleSampleValueChange = (key: string, value: string) => {
    const updated = { ...sampleData, [key]: value };
    setSampleData(updated);

    // Live update preview if modal is open
    let liveSubject = subject;
    let liveBody = body;
    Object.entries(updated).forEach(([k, v]) => {
      const reg = new RegExp(`\\{\\{${k}\\}\\}`, "g");
      liveSubject = liveSubject.replace(reg, v);
      liveBody = liveBody.replace(reg, v);
    });
    setPreviewSubject(liveSubject);
    setPreviewBody(liveBody);
  };

  if (loading) {
    return (
      <div className={styles.loadingContainer}>
        <Loader2 size={24} className={styles.spinner} />
        <span>Loading template editor…</span>
      </div>
    );
  }

  if (error && !template) {
    return (
      <div className={styles.page}>
        <div className={styles.errorBox}>
          <AlertCircle size={20} />
          <span>{error}</span>
        </div>
        <button type="button" className={styles.backButton} onClick={() => navigate(-1)}>
          <ArrowLeft size={16} /> Back to Configurations
        </button>
      </div>
    );
  }

  if (!template) return null;

  return (
    <div className={styles.page}>
      {/* Top Navbar / Breadcrumb */}
      <header className={styles.header}>
        <div className={styles.leftNav}>
          <Link to={appPath("/app/configurations")} className={styles.backLink}>
            <ArrowLeft size={18} />
            <span>Configurations</span>
          </Link>
          <span className={styles.divider}>/</span>
          <span className={styles.currentTitle}>{template.display_name}</span>
        </div>

        <div className={styles.headerActions}>
          <button
            type="button"
            className={styles.secondaryButton}
            onClick={handleOpenPreview}
            disabled={saving || resetting}
          >
            <Eye size={16} />
            Preview
          </button>

          {template.is_customized && (
            <button
              type="button"
              className={styles.dangerButton}
              onClick={() => setIsResetConfirmOpen(true)}
              disabled={saving || resetting}
            >
              <RotateCcw size={16} />
              Reset to Default
            </button>
          )}

          <button
            type="button"
            className={styles.primaryButton}
            onClick={handleSave}
            disabled={saving || resetting}
          >
            {saving ? (
              <Loader2 size={16} className={styles.spinner} />
            ) : (
              <Save size={16} />
            )}
            Save Changes
          </button>
        </div>
      </header>

      {/* Status Banners */}
      {error && (
        <div className={styles.errorBanner}>
          <AlertCircle size={18} />
          <span>{error}</span>
        </div>
      )}

      {successMessage && (
        <div className={styles.successBanner}>
          <Check size={18} />
          <span>{successMessage}</span>
        </div>
      )}

      {/* Editor Grid */}
      <fieldset
        className={styles.editorFields}
        disabled={saving || resetting}
        aria-busy={saving || resetting}
      >
      <div className={styles.editorGrid}>
        {/* Main Editor Panel */}
        <div className={styles.mainPanel}>
          <div className={styles.panelHeader}>
            <div>
              <h2 className={styles.templateTitle}>{template.display_name}</h2>
              <p className={styles.templateDesc}>{template.description}</p>
            </div>
            <div className={styles.badges}>
              <span className={styles.typeBadge}>{template.template_type}</span>
              {template.is_customized ? (
                <span className={`${styles.statusBadge} ${styles.customizedBadge}`}>
                  <SlidersHorizontal size={12} /> Customized
                </span>
              ) : (
                <span className={`${styles.statusBadge} ${styles.defaultBadge}`}>
                  <CheckCircle2 size={12} /> Platform Default
                </span>
              )}
            </div>
          </div>

          {/* Subject Field (if applicable) */}
          {(template.subject !== null || template.default_subject !== null) && (
            <div className={styles.fieldGroup}>
              <label htmlFor="template-subject" className={styles.fieldLabel}>
                Subject Line
              </label>
              <input
                id="template-subject"
                type="text"
                className={styles.subjectInput}
                value={subject}
                onChange={(event) => {
                  const nextSubject = event.target.value;
                  draftRef.current = { ...draftRef.current, subject: nextSubject };
                  setSubject(nextSubject);
                }}
                placeholder="Enter email subject..."
              />
            </div>
          )}

          {/* Body Textarea Editor */}
          <div className={styles.fieldGroup}>
            <div className={styles.editorLabelRow}>
              <label htmlFor="template-body" className={styles.fieldLabel}>
                Template Body (Markdown)
              </label>
              <span className={styles.editorHint}>
                Use <code>{`{{placeholder}}`}</code> variables to insert dynamic text.
              </span>
            </div>
            <textarea
              id="template-body"
              className={styles.bodyTextarea}
              value={body}
              onChange={(event) => {
                const nextBody = event.target.value;
                draftRef.current = { ...draftRef.current, body: nextBody };
                setBody(nextBody);
              }}
              rows={16}
              placeholder="Write template body in Markdown..."
            />
          </div>
        </div>

        {/* Sidebar: Available Placeholders */}
        <aside className={styles.sidePanel}>
          <div className={styles.placeholderCard}>
            <div className={styles.placeholderHeader}>
              <Tag size={16} className={styles.tagIcon} />
              <h3>Available Variables</h3>
            </div>
            <p className={styles.placeholderHint}>
              Click any variable to append it into your template body:
            </p>

            <div className={styles.placeholderList}>
              {template.placeholders.length === 0 ? (
                <p className={styles.noPlaceholders}>No placeholders available for this template.</p>
              ) : (
                template.placeholders.map((ph) => (
                  <button
                    key={ph.key}
                    type="button"
                    className={styles.placeholderPill}
                    onClick={() => handleInsertPlaceholder(ph.key)}
                    title={`Click to insert {{${ph.key}}}`}
                  >
                    <span className={styles.phKey}>{`{{${ph.key}}}`}</span>
                    <span className={styles.phLabel}>{ph.label}</span>
                    {ph.required && <span className={styles.reqBadge}>Required</span>}
                  </button>
                ))
              )}
            </div>
          </div>

          <div className={styles.infoCard}>
            <FileCode2 size={16} />
            <div>
              <strong>Markdown Supported</strong>
              <p>Supports headers (#), bold (**), lists (-), links, and tables.</p>
            </div>
          </div>
        </aside>
      </div>
      </fieldset>

      {/* Live Preview Modal */}
      <TemplatePreviewModal
        isOpen={isPreviewOpen}
        onClose={() => setIsPreviewOpen(false)}
        title={template.display_name}
        subject={previewSubject}
        body={previewBody}
        sampleData={sampleData}
        onSampleDataChange={handleSampleValueChange}
      />

      {/* Reset Confirmation Dialog */}
      {isResetConfirmOpen && (
        <div className={styles.modalOverlay} onClick={() => setIsResetConfirmOpen(false)}>
          <div className={styles.confirmModal} onClick={(e) => e.stopPropagation()}>
            <h3>Reset to Platform Default?</h3>
            <p>
              This will delete your customized template and restore SmartSkale's platform default
              version. This action cannot be undone.
            </p>
            <div className={styles.confirmActions}>
              <button
                type="button"
                className={styles.cancelBtn}
                onClick={() => setIsResetConfirmOpen(false)}
              >
                Cancel
              </button>
              <button
                type="button"
                className={styles.dangerBtn}
                onClick={handleReset}
                disabled={resetting}
              >
                {resetting ? "Resetting…" : "Yes, Reset to Default"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
