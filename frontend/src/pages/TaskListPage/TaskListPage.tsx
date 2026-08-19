import { Plus } from "lucide-react";
import { useState } from "react";
import { useSearchParams } from "react-router-dom";

import { useSession } from "../../entities/session/model/session-context";
import { taskManagementApi } from "../../features/task-management/api/task-management-api";
import { canCreateTask, canManageProject } from "../../features/task-management/model/permissions";
import { DEFAULT_PAGE_SIZE } from "../../features/task-management/model/constants";
import type { Task, TaskFilters as ApiTaskFilters } from "../../features/task-management/model/types";
import { useMembers, useProjects, useTaskMutation, useTasks, useUsers } from "../../features/task-management/model/use-task-management";
import { TaskFilters, type TaskFilterValues } from "../../features/task-management/ui/TaskFilters/TaskFilters";
import { TaskForm } from "../../features/task-management/ui/TaskForm/TaskForm";
import { TaskTable } from "../../features/task-management/ui/TaskTable/TaskTable";
import { ErrorState, LoadingState, Overlay, PageHeading } from "../../features/task-management/ui/primitives";
import { TaskDrawer } from "../../features/task-management/ui/TaskDrawer/TaskDrawer";
import styles from "../../features/task-management/ui/task-management.module.css";
import { Button } from "../../shared/ui/Button/Button";
import { ConfirmDialog } from "../../shared/ui/ConfirmDialog/ConfirmDialog";

export const TaskListPage = ({ mode }: { mode: "all" | "mine" }) => {
  const { principal } = useSession();
  const [params, setParams] = useSearchParams();
  const [creating, setCreating] = useState(false);
  const [archiveTarget, setArchiveTarget] = useState<Task | null>(null);
  const projectsQuery = useProjects({ page_size: 100, include_archived: true, sort: "project_key" });
  const usersQuery = useUsers();
  const selectedProjectId = params.get("project_id") ?? "";
  const membersQuery = useMembers(selectedProjectId || undefined);
  const tenantPrincipal = principal?.principal_type === "tenant_user" ? principal : null;
  const filterValues: TaskFilterValues = Object.fromEntries(["query", "project_id", "status", "priority", "task_type", "assignee_id", "reporter_id", "member_id", "due_from", "due_to", "archived", "sort"].map((key) => [key, params.get(key) ?? undefined]));
  const page = Math.max(1, Number(params.get("page")) || 1);
  const filters: ApiTaskFilters = { ...filterValues as ApiTaskFilters, page, page_size: DEFAULT_PAGE_SIZE, archived: filterValues.archived === "true" ? true : undefined, assignee_id: mode === "mine" ? tenantPrincipal?.principal_id : filterValues.assignee_id, sort: filterValues.sort ?? "-updated_at" };
  const tasks = useTasks(filters);
  const member = membersQuery.data?.items.find((item) => item.user_id === tenantPrincipal?.principal_id);
  const access = { tenantRole: tenantPrincipal?.role ?? "Employee", memberRole: member?.role, principalId: tenantPrincipal?.principal_id ?? "" };
  const selectedProject = projectsQuery.data?.items.find((project) => project.project_id === selectedProjectId);
  const mayCreate = Boolean(selectedProject && !selectedProject.archived_at && canCreateTask(access));
  const archiveMutation = useTaskMutation(({ task, next }: { task: Task; next: boolean }) => taskManagementApi.setTaskArchived(task, next));
  if (!tenantPrincipal) return null;
  const updateFilters = (next: TaskFilterValues) => { const output = new URLSearchParams(params); ["query", "project_id", "status", "priority", "task_type", "assignee_id", "reporter_id", "member_id", "due_from", "due_to", "archived", "sort"].forEach((key) => { const value = next[key as keyof TaskFilterValues]; if (value) output.set(key, value); else output.delete(key); }); output.set("page", "1"); setParams(output, { replace: true }); };
  const setPage = (next: number) => { const output = new URLSearchParams(params); output.set("page", String(next)); setParams(output, { replace: true }); };
  const openTask = (task: Task) => { const output = new URLSearchParams(params); output.set("task", task.task_id); setParams(output); };
  const closeTask = () => { const output = new URLSearchParams(params); output.delete("task"); setParams(output, { replace: true }); };
  return <div className={styles.content}>
    <PageHeading eyebrow="Task Management" title={mode === "mine" ? "My Work" : "All Tasks"} description={mode === "mine" ? "Work assigned to you across every accessible project." : "Search, filter and inspect work across your accessible projects."} actions={mayCreate ? <Button type="button" className={styles.compactButton} onClick={() => setCreating(true)}><Plus size={14} /> New task</Button> : undefined} />
    <TaskFilters value={filterValues} projects={projectsQuery.data?.items ?? []} users={usersQuery.data ?? []} onChange={updateFilters} />
    <section className={styles.panel}>{tasks.isPending ? <LoadingState /> : tasks.isError ? <ErrorState message={tasks.error.message} onRetry={() => void tasks.refetch()} /> : <TaskTable tasks={tasks.data.items} total={tasks.data.total} page={page} pageSize={DEFAULT_PAGE_SIZE} projects={projectsQuery.data?.items ?? []} users={usersQuery.data ?? []} filtered={Object.values(filterValues).some(Boolean)} onOpen={openTask} onPageChange={setPage} onArchive={canManageProject(access) ? (task) => setArchiveTarget(task) : undefined} />}</section>
    <Overlay open={creating} title="Create task" description={selectedProject ? `${selectedProject.project_key} · ${selectedProject.name}` : undefined} mode="drawer" wide guardDirtyForm onClose={() => setCreating(false)}>{selectedProject && <TaskForm projectId={selectedProject.project_id} users={usersQuery.data ?? []} managerFields={canManageProject(access)} onCancel={() => setCreating(false)} onSaved={(task) => { setCreating(false); openTask(task); }} />}</Overlay>
    <TaskDrawer taskId={params.get("task") ?? undefined} projects={projectsQuery.data?.items ?? []} users={usersQuery.data ?? []} onClose={closeTask} />
    <ConfirmDialog open={Boolean(archiveTarget)} title={archiveTarget?.archived_at ? "Restore this task?" : "Archive this task?"} description={archiveTarget?.archived_at ? "The task will return to active work." : "The task becomes read-only while its history remains available."} confirmLabel={archiveTarget?.archived_at ? "Restore task" : "Archive task"} destructive={!archiveTarget?.archived_at} busy={archiveMutation.isPending} onCancel={() => setArchiveTarget(null)} onConfirm={() => { if (!archiveTarget) return; void archiveMutation.mutateAsync({ task: archiveTarget, next: !archiveTarget.archived_at }).then(() => setArchiveTarget(null)); }} />
  </div>;
};
