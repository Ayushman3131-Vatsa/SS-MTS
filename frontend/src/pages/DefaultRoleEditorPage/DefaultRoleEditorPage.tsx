import { ArrowLeft, Save, Search, ShieldCheck, Trash2 } from "lucide-react";
import { useEffect, useMemo, useState, type FormEvent } from "react";
import { Link, useBlocker, useNavigate, useParams, useSearchParams } from "react-router-dom";

import { defaultRolesApi } from "../../features/default-role-management/api/default-roles-api";
import {
  ACCESS_LEVELS,
  accessLevelLabel,
  type AccessLevel,
  type DefaultRoleDetail,
  type DefaultRolePageAccess,
} from "../../features/default-role-management/model/default-roles";
import { offeringsApi } from "../../features/offering-management/api/offerings-api";
import type { OfferingCatalogItem } from "../../features/offering-management/model/offerings";
import { ApiError } from "../../shared/api/errors";
import { Alert } from "../../shared/ui/Alert/Alert";
import { Button } from "../../shared/ui/Button/Button";
import { ConfirmDialog } from "../../shared/ui/ConfirmDialog/ConfirmDialog";
import { InputField } from "../../shared/ui/InputField/InputField";
import styles from "./DefaultRoleEditorPage.module.css";

interface EditorValues {
  role_name: string;
  role_code: string;
  description: string;
  offering_id: string;
  is_active: boolean;
  page_access: DefaultRolePageAccess[];
}

const toRoleCode = (name: string) =>
  name.trim().toUpperCase().replace(/[^A-Z0-9]+/g, "_").replace(/^_+|_+$/g, "") || "CUSTOM_ROLE";

const blankEditor = (offeringId = ""): EditorValues => ({
  role_name: "",
  role_code: "",
  description: "",
  offering_id: offeringId,
  is_active: true,
  page_access: [],
});

const editorFromDetail = (detail: DefaultRoleDetail): EditorValues => ({
  role_name: detail.role_name,
  role_code: detail.role_code,
  description: detail.description ?? "",
  offering_id: detail.offering_id ?? "",
  is_active: detail.is_active,
  page_access: detail.page_access,
});

const serializeEditor = (editor: EditorValues) => JSON.stringify(editor);

const errorMessage = (caught: unknown) =>
  caught instanceof ApiError ? caught.message : caught instanceof Error ? caught.message : "The role could not be saved.";

export const DefaultRoleEditorPage = () => {
  const navigate = useNavigate();
  const { roleId } = useParams();
  const [searchParams] = useSearchParams();
  const isNew = !roleId || roleId === "new";
  const initialOfferingId = searchParams.get("offering_id") ?? "";
  const [offerings, setOfferings] = useState<OfferingCatalogItem[]>([]);
  const [editor, setEditor] = useState<EditorValues>(blankEditor(initialOfferingId));
  const [baseline, setBaseline] = useState(serializeEditor(blankEditor(initialOfferingId)));
  const [version, setVersion] = useState(1);
  const [isSystem, setIsSystem] = useState(false);
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(!isNew);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [deleteOpen, setDeleteOpen] = useState(false);
  const dirty = serializeEditor(editor) !== baseline;

  const blocker = useBlocker(dirty && !saving);

  useEffect(() => {
    const controller = new AbortController();
    void offeringsApi.list(controller.signal).then(setOfferings).catch(() => setOfferings([]));
    return () => controller.abort();
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    if (isNew) {
      void defaultRolesApi
        .pages({ offeringId: initialOfferingId || null, signal: controller.signal })
        .then((catalog) => {
          const next = {
            ...blankEditor(initialOfferingId),
            page_access: catalog.pages.map((page) => ({ page, access_level: "none" as AccessLevel })),
          };
          setEditor(next);
          setBaseline(serializeEditor(next));
        })
        .catch((caught: unknown) => setError(errorMessage(caught)));
      return () => controller.abort();
    }
    setLoading(true);
    void defaultRolesApi
      .get(roleId, controller.signal)
      .then((detail) => {
        const next = editorFromDetail(detail);
        setEditor(next);
        setBaseline(serializeEditor(next));
        setVersion(detail.version);
        setIsSystem(detail.is_system);
      })
      .catch((caught: unknown) => setError(errorMessage(caught)))
      .finally(() => setLoading(false));
    return () => controller.abort();
  }, [initialOfferingId, isNew, roleId]);

  const selectedOffering = offerings.find((item) => item.offering_id === editor.offering_id);
  const moduleLabel = selectedOffering?.display_name ?? "Workspace";
  const listReturn = editor.offering_id
    ? `/platform/roles?type=tenant&offering_id=${encodeURIComponent(editor.offering_id)}`
    : "/platform/roles?type=tenant";

  const visibleAccess = useMemo(() => {
    const needle = query.trim().toLowerCase();
    if (!needle) return editor.page_access;
    return editor.page_access.filter((entry) =>
      `${entry.page.page_name} ${entry.page.page_code} ${entry.page.route}`.toLowerCase().includes(needle),
    );
  }, [editor.page_access, query]);

  const counts = useMemo(() => {
    const tally = { none: 0, view: 0, modify: 0 };
    for (const entry of editor.page_access) tally[entry.access_level] += 1;
    return tally;
  }, [editor.page_access]);

  const setAllAccess = (level: AccessLevel) => {
    setEditor((current) => ({
      ...current,
      page_access: current.page_access.map((entry) => ({ ...entry, access_level: level })),
    }));
  };

  const setPageAccess = (pageId: string, level: AccessLevel) => {
    setEditor((current) => ({
      ...current,
      page_access: current.page_access.map((entry) =>
        entry.page.page_id === pageId ? { ...entry, access_level: level } : entry,
      ),
    }));
  };

  const handleSave = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setSaving(true);
    setError(null);
    const entries = editor.page_access.map((entry) => ({
      page_id: entry.page.page_id,
      access_level: entry.access_level,
    }));
    try {
      if (isNew) {
        const created = await defaultRolesApi.create({
          role_name: editor.role_name,
          role_code: toRoleCode(editor.role_code || editor.role_name),
          description: editor.description || null,
          offering_id: editor.offering_id || null,
          entries,
        });
        setBaseline(serializeEditor(editorFromDetail(created)));
        navigate(`/platform/default-roles/${created.role_id}`, { replace: true });
        return;
      }
      const updated = await defaultRolesApi.update(roleId, {
        role_name: editor.role_name,
        description: editor.description || null,
        is_active: editor.is_active,
        version,
        entries,
      });
      const next = editorFromDetail(updated);
      setEditor(next);
      setBaseline(serializeEditor(next));
      setVersion(updated.version);
    } catch (caught) {
      setError(errorMessage(caught));
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async () => {
    if (!roleId || isNew || isSystem) return;
    setSaving(true);
    setError(null);
    try {
      await defaultRolesApi.delete(roleId);
      navigate(listReturn, { replace: true });
    } catch (caught) {
      setError(errorMessage(caught));
      setSaving(false);
    }
  };

  if (loading) {
    return <div className={styles.page} role="status">Loading role template…</div>;
  }

  return (
    <form className={styles.page} onSubmit={(event) => void handleSave(event)}>
      <header className={styles.topbar}>
        <div className={styles.breadcrumb}>
          <Link to={listReturn}>
            <ArrowLeft size={15} aria-hidden="true" />
            Roles & Permissions
          </Link>
          <span aria-hidden="true">/</span>
          <strong>{isNew ? "New role" : editor.role_name || "Role template"}</strong>
        </div>
        <div className={styles.topActions}>
          {dirty ? <span className={styles.dirtyStatus}>Unsaved</span> : <span className={styles.savedStatus}>Saved</span>}
          {!isNew && !isSystem && (
            <Button type="button" variant="secondary" onClick={() => setDeleteOpen(true)} disabled={saving}>
              <Trash2 size={15} aria-hidden="true" />
              Delete
            </Button>
          )}
          <Button type="submit" loading={saving} loadingLabel="Saving…">
            <Save size={15} aria-hidden="true" />
            Save
          </Button>
        </div>
      </header>

      <div className={styles.content}>
        <div className={styles.titleBlock}>
          <div>
            <p>Permission template</p>
            <h1>{isNew ? "New default role" : editor.role_name}</h1>
            <span>Set None, View, or Modify for each page in {moduleLabel}.</span>
          </div>
          {isSystem && <span className={styles.systemBadge}><ShieldCheck size={14} aria-hidden="true" /> System role</span>}
        </div>

        {error && <Alert tone="error" title="Could not save">{error}</Alert>}

        <section className={styles.card}>
          <h2>Role details</h2>
          <div className={styles.formGrid}>
            <InputField
              id="default-role-name"
              label="Role name"
              value={editor.role_name}
              onChange={(event) => {
                const role_name = event.target.value;
                setEditor((current) => ({
                  ...current,
                  role_name,
                  role_code: isNew && (!current.role_code || current.role_code === toRoleCode(current.role_name))
                    ? toRoleCode(role_name)
                    : current.role_code,
                }));
              }}
              required
            />
            <InputField
              id="default-role-code"
              label="Role code"
              value={editor.role_code}
              onChange={(event) => setEditor((current) => ({ ...current, role_code: toRoleCode(event.target.value) }))}
              disabled={!isNew}
              hint={isNew ? "Generated from the name. Must be unique in this module." : "Role codes cannot change after create."}
              required
            />
            <label className={styles.span2}>
              Description
              <textarea
                value={editor.description}
                onChange={(event) => setEditor((current) => ({ ...current, description: event.target.value }))}
                rows={3}
                maxLength={1000}
                placeholder="When should a tenant assign this role?"
              />
            </label>
            {isNew ? (
              <label>
                Module
                <select
                  value={editor.offering_id}
                  onChange={(event) => {
                    const nextOfferingId = event.target.value;
                    setEditor((current) => ({ ...current, offering_id: nextOfferingId, page_access: [] }));
                    void defaultRolesApi.pages({ offeringId: nextOfferingId || null }).then((catalog) => {
                      setEditor((current) => ({
                        ...current,
                        offering_id: nextOfferingId,
                        page_access: catalog.pages.map((page) => ({ page, access_level: "none" })),
                      }));
                    });
                  }}
                >
                  <option value="">Workspace (core)</option>
                  {offerings.map((offering) => (
                    <option key={offering.offering_id} value={offering.offering_id}>
                      {offering.display_name}
                    </option>
                  ))}
                </select>
              </label>
            ) : (
              <label className={styles.toggle}>
                <input
                  type="checkbox"
                  checked={editor.is_active}
                  onChange={(event) => setEditor((current) => ({ ...current, is_active: event.target.checked }))}
                />
                Active template
              </label>
            )}
          </div>
        </section>

        <section className={styles.card}>
          <div className={styles.matrixHeader}>
            <div>
              <h2>Page access</h2>
              <p>{counts.modify} modify · {counts.view} view · {counts.none} none</p>
            </div>
            <div className={styles.bulk}>
              <button type="button" onClick={() => setAllAccess("none")}>None</button>
              <button type="button" onClick={() => setAllAccess("view")}>View all</button>
              <button type="button" onClick={() => setAllAccess("modify")}>Modify all</button>
            </div>
          </div>
          <label className={styles.searchField}>
            <Search size={16} aria-hidden="true" />
            <span className={styles.srOnly}>Search pages</span>
            <input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search pages" />
          </label>
          {visibleAccess.length === 0 ? (
            <div className={styles.emptyPages}>No pages in this module yet.</div>
          ) : (
            <div className={styles.pageList}>
              {visibleAccess.map((entry) => (
                <div className={styles.pageRow} key={entry.page.page_id}>
                  <div>
                    <strong>{entry.page.page_name}</strong>
                    <small>{entry.page.page_code}</small>
                  </div>
                  <div className={styles.segmented} role="group" aria-label={`${entry.page.page_name} access`}>
                    {ACCESS_LEVELS.map((level) => (
                      <button
                        type="button"
                        key={level}
                        className={
                          entry.access_level === level
                            ? `${styles.segmentActive} ${level === "view" ? styles.segmentView : ""} ${level === "none" ? styles.segmentNone : ""}`
                            : ""
                        }
                        onClick={() => setPageAccess(entry.page.page_id, level)}
                      >
                        {accessLevelLabel[level]}
                      </button>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          )}
        </section>
      </div>

      <ConfirmDialog
        open={deleteOpen}
        title="Delete this default role?"
        description="Tenants that already received a copy keep it. New tenants will not get this template."
        confirmLabel="Delete role"
        destructive
        busy={saving}
        onCancel={() => setDeleteOpen(false)}
        onConfirm={() => void handleDelete()}
      />
      <ConfirmDialog
        open={blocker.state === "blocked"}
        title="Leave without saving?"
        description="Your permission changes will be lost."
        confirmLabel="Leave"
        destructive
        onCancel={() => blocker.reset?.()}
        onConfirm={() => blocker.proceed?.()}
      />
    </form>
  );
};
