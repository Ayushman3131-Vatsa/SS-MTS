import { Archive, Plus, RotateCcw } from "lucide-react";
import { useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";

import { useSession } from "../../entities/session/model/session-context";
import { taskManagementApi } from "../../features/task-management/api/task-management-api";
import { canCreateProject } from "../../features/task-management/model/permissions";
import { formatDate } from "../../features/task-management/model/format";
import type { Project, ProjectStatus } from "../../features/task-management/model/types";
import { useProjects, useTaskMutation } from "../../features/task-management/model/use-task-management";
import { ProjectFilters } from "../../features/task-management/ui/TaskFilters/TaskFilters";
import { EmptyState, ErrorState, LoadingState, Overlay, PageHeading, Pagination, PriorityBadge, StatusBadge } from "../../features/task-management/ui/primitives";
import { ProjectForm } from "../../features/task-management/ui/ProjectForm/ProjectForm";
import styles from "../../features/task-management/ui/task-management.module.css";
import { Button } from "../../shared/ui/Button/Button";
import { ConfirmDialog } from "../../shared/ui/ConfirmDialog/ConfirmDialog";

export const TaskProjectsPage = () => {
  const { principal } = useSession();
  const navigate = useNavigate();
  const [params, setParams] = useSearchParams();
  const [creating, setCreating] = useState(false);
  const [archiveTarget, setArchiveTarget] = useState<Project | null>(null);
  const page = Math.max(1, Number(params.get("page")) || 1);
  const query = params.get("query") ?? "";
  const status = params.get("status") ?? "";
  const archived = params.get("archived") ?? "";
  const sort = params.get("sort") ?? "-updated_at";
  const projects = useProjects({ page, page_size: 25, query: query || undefined, status: status as ProjectStatus || undefined, include_archived: archived === "true", sort });
  const archiveMutation = useTaskMutation(({ project, next }: { project: Project; next: boolean }) => taskManagementApi.setProjectArchived(project, next));
  if (!principal || principal.principal_type !== "tenant_user") return null;
  const update = (key: string, value: string) => { const next = new URLSearchParams(params); if (value) next.set(key, value); else next.delete(key); if (key !== "page") next.set("page", "1"); setParams(next, { replace: true }); };
  const items = projects.data?.items ?? [];
  return <div className={styles.content}>
    <PageHeading eyebrow="Task Management" title="Projects" description="Plan, staff and track every delivery workspace." actions={canCreateProject(principal) ? <Button type="button" className={styles.compactButton} onClick={() => setCreating(true)}><Plus size={14} /> New project</Button> : undefined} />
    <ProjectFilters query={query} status={status} archived={archived} sort={sort} onChange={update} />
    <section className={styles.panel}>
      {projects.isPending ? <LoadingState /> : projects.isError ? <ErrorState message={projects.error.message} onRetry={() => void projects.refetch()} /> : items.length === 0 ? <EmptyState title={query || status ? "No projects match these filters" : "No projects yet"} description={query || status ? "Try another search or status." : "Create your first project to start planning work."} /> : <><div className={styles.tableWrap}><table className={styles.table}><thead><tr><th>Key</th><th>Project</th><th>Client</th><th>Status</th><th>Priority</th><th>Dates</th><th>Updated</th><th aria-label="Actions" /></tr></thead><tbody>{items.map((project) => <tr key={project.project_id}><td><button type="button" className={styles.linkButton} onClick={() => navigate(`${project.project_id}/board`)}>{project.project_key}</button></td><td><button type="button" className={styles.linkButton} onClick={() => navigate(`${project.project_id}/board`)}>{project.name}</button>{project.archived_at && <span className={styles.archivedNote}>Archived · read only</span>}</td><td>{project.client_name ?? "—"}</td><td><StatusBadge value={project.status} /></td><td><PriorityBadge value={project.priority} /></td><td>{formatDate(project.start_date)} – {formatDate(project.expected_end_date)}</td><td>{formatDate(project.updated_at, true)}</td><td><div className={styles.rowActions}><Button type="button" variant="ghost" title={project.archived_at ? "Restore" : "Archive"} aria-label={`${project.archived_at ? "Restore" : "Archive"} ${project.name}`} onClick={() => setArchiveTarget(project)}>{project.archived_at ? <RotateCcw size={14} /> : <Archive size={14} />}</Button></div></td></tr>)}</tbody></table></div><Pagination page={page} pageSize={25} total={projects.data?.total ?? 0} onPageChange={(next) => update("page", String(next))} /></>}
    </section>
    <Overlay open={creating} title="Create project" description="A manager membership is created automatically." onClose={() => setCreating(false)} wide guardDirtyForm><ProjectForm onCancel={() => setCreating(false)} onSaved={(project) => { setCreating(false); navigate(`${project.project_id}/board`); }} /></Overlay>
    <ConfirmDialog open={Boolean(archiveTarget)} title={archiveTarget?.archived_at ? "Restore this project?" : "Archive this project?"} description={archiveTarget?.archived_at ? "The project and its history will become active again." : "The project becomes read-only. Tasks and history are retained."} confirmLabel={archiveTarget?.archived_at ? "Restore project" : "Archive project"} destructive={!archiveTarget?.archived_at} busy={archiveMutation.isPending} onCancel={() => setArchiveTarget(null)} onConfirm={() => { if (!archiveTarget) return; void archiveMutation.mutateAsync({ project: archiveTarget, next: !archiveTarget.archived_at }).then(() => setArchiveTarget(null)); }} />
  </div>;
};
