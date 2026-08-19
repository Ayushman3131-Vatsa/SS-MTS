import { ChevronLeft, ChevronRight, Inbox, X } from "lucide-react";
import {
  type PropsWithChildren,
  type ReactNode,
  useCallback,
  useEffect,
  useId,
  useRef,
  useState,
} from "react";
import { createPortal } from "react-dom";

import { Button } from "../../../shared/ui/Button/Button";
import { ConfirmDialog } from "../../../shared/ui/ConfirmDialog/ConfirmDialog";
import type { Priority, ProjectStatus, TaskStatus, TaskType, UserSummary } from "../model/types";
import styles from "./task-management.module.css";

export const StatusBadge = ({ value }: { value: ProjectStatus | TaskStatus }) => (
  <span className={`${styles.badge} ${styles[`status${value.replaceAll(" ", "")}`] ?? ""}`}>{value}</span>
);

export const PriorityBadge = ({ value }: { value: Priority }) => (
  <span className={`${styles.badge} ${styles[`priority${value}`]}`}>{value}</span>
);

export const TypeBadge = ({ value }: { value: TaskType }) => (
  <span className={`${styles.typeBadge} ${styles[`type${value}`]}`}>{value}</span>
);

export const UserAvatar = ({ user, size = "small" }: { user?: UserSummary; size?: "small" | "medium" }) => (
  <span className={`${styles.avatar} ${size === "medium" ? styles.avatarMedium : ""}`} title={user?.name ?? "Unassigned"} aria-label={user?.name ?? "Unassigned"}>
    {user?.name.slice(0, 2).toUpperCase() ?? "—"}
  </span>
);

export const PageHeading = ({
  eyebrow,
  title,
  description,
  actions,
}: {
  eyebrow?: string;
  title: string;
  description?: string;
  actions?: ReactNode;
}) => (
  <header className={styles.pageHeading}>
    <div>{eyebrow && <span>{eyebrow}</span>}<h1>{title}</h1>{description && <p>{description}</p>}</div>
    {actions && <div className={styles.headingActions}>{actions}</div>}
  </header>
);

export const EmptyState = ({ title, description, action }: { title: string; description: string; action?: ReactNode }) => (
  <div className={styles.emptyState}>
    <Inbox size={25} aria-hidden="true" />
    <strong>{title}</strong>
    <p>{description}</p>
    {action}
  </div>
);

export const LoadingState = ({ rows = 5 }: { rows?: number }) => (
  <div className={styles.skeleton} aria-label="Loading" role="status">
    {Array.from({ length: rows }, (_, index) => <span key={index} />)}
  </div>
);

export const ErrorState = ({ message, onRetry }: { message?: string; onRetry: () => void }) => (
  <div className={styles.errorState} role="alert">
    <div><strong>We couldn’t load this view.</strong><span>{message ?? "Check your connection and try again."}</span></div>
    <Button type="button" variant="secondary" onClick={onRetry}>Retry</Button>
  </div>
);

export const Pagination = ({ page, pageSize, total, onPageChange }: { page: number; pageSize: number; total: number; onPageChange: (page: number) => void }) => {
  const pages = Math.max(1, Math.ceil(total / pageSize));
  return (
    <nav className={styles.pagination} aria-label="Pagination">
      <span>{total === 0 ? "0 items" : `${(page - 1) * pageSize + 1}–${Math.min(page * pageSize, total)} of ${total}`}</span>
      <Button type="button" variant="ghost" disabled={page <= 1} aria-label="Previous page" onClick={() => onPageChange(page - 1)}><ChevronLeft size={16} /></Button>
      <strong>{page} / {pages}</strong>
      <Button type="button" variant="ghost" disabled={page >= pages} aria-label="Next page" onClick={() => onPageChange(page + 1)}><ChevronRight size={16} /></Button>
    </nav>
  );
};

interface OverlayProps extends PropsWithChildren {
  open: boolean;
  title: string;
  description?: string;
  mode?: "drawer" | "modal";
  wide?: boolean;
  guardDirtyForm?: boolean;
  onClose: () => void;
}

export const Overlay = ({ open, title, description, mode = "modal", wide = false, guardDirtyForm = false, onClose, children }: OverlayProps) => {
  const titleId = useId();
  const panelRef = useRef<HTMLElement>(null);
  const returnFocusRef = useRef<HTMLElement | null>(null);
  const [dirty, setDirty] = useState(false);
  const [confirmClose, setConfirmClose] = useState(false);
  const requestClose = useCallback(() => {
    if (guardDirtyForm && dirty) setConfirmClose(true);
    else onClose();
  }, [dirty, guardDirtyForm, onClose]);

  useEffect(() => {
    if (open) { setDirty(false); setConfirmClose(false); }
  }, [open]);

  useEffect(() => {
    if (!open) return;
    returnFocusRef.current = document.activeElement as HTMLElement | null;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    window.setTimeout(() => panelRef.current?.querySelector<HTMLElement>("button, input, select, textarea")?.focus(), 0);
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") requestClose();
      if (event.key !== "Tab") return;
      const elements = Array.from(panelRef.current?.querySelectorAll<HTMLElement>('button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), a[href], [tabindex]:not([tabindex="-1"])') ?? []);
      if (!elements.length) return;
      const first = elements[0];
      const last = elements.at(-1)!;
      if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
      if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
    };
    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("keydown", onKeyDown);
      document.body.style.overflow = previousOverflow;
      returnFocusRef.current?.focus();
    };
  }, [open, requestClose]);

  if (!open) return null;
  return createPortal(
    <><div className={`${styles.overlay} ${mode === "drawer" ? styles.drawerOverlay : ""}`} role="presentation" onMouseDown={(event) => { if (event.target === event.currentTarget) requestClose(); }}>
      <section ref={panelRef} onChangeCapture={() => { if (guardDirtyForm) setDirty(true); }} className={`${styles.overlayPanel} ${mode === "drawer" ? styles.drawer : styles.modal} ${wide ? styles.wide : ""}`} role="dialog" aria-modal="true" aria-labelledby={titleId}>
        <header className={styles.overlayHeader}>
          <div><h2 id={titleId}>{title}</h2>{description && <p>{description}</p>}</div>
          <button type="button" aria-label={`Close ${title}`} onClick={requestClose}><X size={19} /></button>
        </header>
        <div className={styles.overlayBody}>{children}</div>
      </section>
    </div><ConfirmDialog open={confirmClose} title="Discard unsaved changes?" description="Your edits in this form have not been saved." confirmLabel="Discard changes" destructive onCancel={() => setConfirmClose(false)} onConfirm={onClose} /></>,
    document.body,
  );
};

export const Field = ({ label, error, children }: PropsWithChildren<{ label: string; error?: string }>) => (
  <label className={styles.field}><span>{label}</span>{children}{error && <small role="alert">{error}</small>}</label>
);
