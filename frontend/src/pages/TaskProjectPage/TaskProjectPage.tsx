import { Archive, ListPlus, RotateCcw, Settings2, UserPlus, Users } from "lucide-react";
import { useState } from "react";
import { NavLink, useNavigate, useParams, useSearchParams } from "react-router-dom";

import { useSession } from "../../entities/session/model/session-context";
import { taskManagementApi } from "../../features/task-management/api/task-management-api";
import { DEFAULT_PAGE_SIZE } from "../../features/task-management/model/constants";
import { formatDate } from "../../features/task-management/model/format";
import { canCreateTask, canExecuteTask, canManageProject } from "../../features/task-management/model/permissions";
import { MEMBER_ROLES, type ProjectMember, type ProjectMemberRole, type Task, type TaskFilters as ApiTaskFilters } from "../../features/task-management/model/types";
import { useMembers, useProject, useProjects, useTaskMutation, useTasks, useUsers } from "../../features/task-management/model/use-task-management";
import { TaskBoard } from "../../features/task-management/ui/TaskBoard/TaskBoard";
import { TaskDrawer } from "../../features/task-management/ui/TaskDrawer/TaskDrawer";
import { TaskFilters, type TaskFilterValues } from "../../features/task-management/ui/TaskFilters/TaskFilters";
import { TaskForm } from "../../features/task-management/ui/TaskForm/TaskForm";
import { TaskTable } from "../../features/task-management/ui/TaskTable/TaskTable";
import { EmptyState, ErrorState, Field, LoadingState, Overlay, PriorityBadge, StatusBadge, UserAvatar } from "../../features/task-management/ui/primitives";
import { ProjectForm } from "../../features/task-management/ui/ProjectForm/ProjectForm";
import styles from "../../features/task-management/ui/task-management.module.css";
import { Button } from "../../shared/ui/Button/Button";
import { ConfirmDialog } from "../../shared/ui/ConfirmDialog/ConfirmDialog";

type ProjectView = "board" | "list" | "members" | "settings";

export const TaskProjectPage = ({ view }: { view: ProjectView }) => {
  const { projectId = "" } = useParams();
  const { principal } = useSession();
  const navigate = useNavigate();
  const [params, setParams] = useSearchParams();
  const [creating, setCreating] = useState(false);
  const [taskArchive, setTaskArchive] = useState<Task | null>(null);
  const projectQuery = useProject(projectId);
  const projectsQuery = useProjects({ page_size: 100, include_archived: true, sort: "project_key" });
  const membersQuery = useMembers(projectId);
  const usersQuery = useUsers();
  const tenantPrincipal = principal?.principal_type === "tenant_user" ? principal : null;
  const membership = membersQuery.data?.items.find((item) => item.user_id === tenantPrincipal?.principal_id);
  const access = { tenantRole: tenantPrincipal?.role ?? "Employee", memberRole: membership?.role, principalId: tenantPrincipal?.principal_id ?? "" };
  const mayManage = canManageProject(access);
  const mayCreate = canCreateTask(access) && !projectQuery.data?.archived_at;
  const filterValues: TaskFilterValues = Object.fromEntries(["query", "status", "priority", "task_type", "assignee_id", "reporter_id", "member_id", "due_from", "due_to", "archived", "sort"].map((key) => [key, params.get(key) ?? undefined]));
  const page = Math.max(1, Number(params.get("page")) || 1);
  const apiFilters: ApiTaskFilters = { ...filterValues as ApiTaskFilters, project_id: projectId, page, page_size: DEFAULT_PAGE_SIZE, archived: filterValues.archived === "true" ? true : undefined, sort: filterValues.sort ?? "-updated_at" };
  const tasksQuery = useTasks(apiFilters);
  const allCount = useTasks({ project_id: projectId, page_size: 1 });
  const completedCount = useTasks({ project_id: projectId, status: "Completed", page_size: 1 });
  const taskArchiveMutation = useTaskMutation(({ task, next }: { task: Task; next: boolean }) => taskManagementApi.setTaskArchived(task, next));
  if (!tenantPrincipal) return null;
  const project = projectQuery.data;
  const updateFilters = (next: TaskFilterValues) => { const output = new URLSearchParams(params); ["query", "status", "priority", "task_type", "assignee_id", "reporter_id", "member_id", "due_from", "due_to", "archived", "sort"].forEach((key) => { const value = next[key as keyof TaskFilterValues]; if (value) output.set(key, value); else output.delete(key); }); output.set("page", "1"); setParams(output, { replace: true }); };
  const openTask = (task: Task) => { const output = new URLSearchParams(params); output.set("task", task.task_id); setParams(output); };
  const closeTask = () => { const output = new URLSearchParams(params); output.delete("task"); setParams(output, { replace: true }); };
  if (projectQuery.isPending) return <LoadingState rows={9} />;
  if (projectQuery.isError) return <ErrorState message={projectQuery.error.message} onRetry={() => void projectQuery.refetch()} />;
  if (!project) return null;
  const progress = allCount.data?.total ? Math.round(((completedCount.data?.total ?? 0) / allCount.data.total) * 100) : 0;
  return <div className={styles.content}>
    <header className={styles.projectHeader}><div><button type="button" onClick={() => navigate("/app/task-management/projects")}>Projects</button><span>/</span><strong>{project.project_key}</strong></div><section><div><h1>{project.name}</h1><p>{project.client_name ?? "Internal project"}</p></div><StatusBadge value={project.status} /><PriorityBadge value={project.priority} />{project.archived_at && <span className={styles.readOnlyFlag}>Archived · read only</span>}<dl><div><dt>Start</dt><dd>{formatDate(project.start_date)}</dd></div><div><dt>Target</dt><dd>{formatDate(project.expected_end_date)}</dd></div><div><dt>Progress</dt><dd>{progress}%</dd></div></dl></section><div className={styles.progressTrack}><span style={{ width: `${progress}%` }} /></div></header>
    <nav className={styles.projectTabs} aria-label="Project workspace"><NavLink to={`/app/task-management/projects/${projectId}/board`}>Board</NavLink><NavLink to={`/app/task-management/projects/${projectId}/list`}>List</NavLink><NavLink to={`/app/task-management/projects/${projectId}/members`}><Users size={14} /> Members</NavLink>{mayManage && <NavLink to={`/app/task-management/projects/${projectId}/settings`}><Settings2 size={14} /> Settings</NavLink>}{mayCreate && <Button type="button" className={styles.compactButton} onClick={() => setCreating(true)}><ListPlus size={14} /> Create task</Button>}</nav>
    {(view === "board" || view === "list") && <TaskFilters value={filterValues} projects={[project]} users={usersQuery.data ?? []} hideProject hideStatus={view === "board"} onChange={updateFilters} />}
    {view === "board" && <TaskBoard projectId={projectId} filters={{ ...apiFilters, status: undefined, page: undefined, page_size: undefined }} users={usersQuery.data ?? []} canMove={(task) => !project.archived_at && (mayManage || canExecuteTask(access, task))} onOpen={openTask} />}
    {view === "list" && <section className={styles.panel}>{tasksQuery.isPending ? <LoadingState /> : tasksQuery.isError ? <ErrorState message={tasksQuery.error.message} onRetry={() => void tasksQuery.refetch()} /> : <TaskTable tasks={tasksQuery.data.items} total={tasksQuery.data.total} page={page} pageSize={DEFAULT_PAGE_SIZE} projects={[project]} users={usersQuery.data ?? []} filtered={Object.values(filterValues).some(Boolean)} onOpen={openTask} onPageChange={(nextPage) => { const output = new URLSearchParams(params); output.set("page", String(nextPage)); setParams(output, { replace: true }); }} onArchive={mayManage ? (task) => setTaskArchive(task) : undefined} />}</section>}
    {view === "members" && <MembersView projectId={projectId} members={membersQuery.data?.items ?? []} users={usersQuery.data ?? []} mayManage={mayManage && !project.archived_at} />}
    {view === "settings" && (mayManage ? <ProjectSettings project={project} /> : <EmptyState title="Settings are restricted" description="Only tenant administrators and project manager members can change project settings." />)}
    <Overlay open={creating} title="Create task" description={`${project.project_key} · ${project.name}`} mode="drawer" wide guardDirtyForm onClose={() => setCreating(false)}><TaskForm projectId={projectId} users={usersQuery.data ?? []} managerFields={mayManage} onCancel={() => setCreating(false)} onSaved={(task) => { setCreating(false); openTask(task); }} /></Overlay>
    <TaskDrawer taskId={params.get("task") ?? undefined} projects={projectsQuery.data?.items ?? [project]} users={usersQuery.data ?? []} onClose={closeTask} />
    <ConfirmDialog open={Boolean(taskArchive)} title={taskArchive?.archived_at ? "Restore this task?" : "Archive this task?"} description={taskArchive?.archived_at ? "The task will return to active work." : "The task becomes read-only while its history stays available."} confirmLabel={taskArchive?.archived_at ? "Restore task" : "Archive task"} destructive={!taskArchive?.archived_at} busy={taskArchiveMutation.isPending} onCancel={() => setTaskArchive(null)} onConfirm={() => { if (!taskArchive) return; void taskArchiveMutation.mutateAsync({ task: taskArchive, next: !taskArchive.archived_at }).then(() => setTaskArchive(null)); }} />
  </div>;
};

const MembersView = ({ projectId, members, users, mayManage }: { projectId: string; members: ProjectMember[]; users: ReturnType<typeof useUsers>["data"] extends infer T ? NonNullable<T> : never; mayManage: boolean }) => {
  const [userId, setUserId] = useState(""); const [role, setRole] = useState<ProjectMemberRole>("MEMBER"); const [confirm, setConfirm] = useState<{ member: ProjectMember; next?: ProjectMemberRole } | null>(null); const [error, setError] = useState<string | null>(null);
  const add = useTaskMutation(() => taskManagementApi.addMember(projectId, userId, role));
  const update = useTaskMutation(({ member, next }: { member: ProjectMember; next: ProjectMemberRole }) => taskManagementApi.updateMember(projectId, member.membership_id, next));
  const remove = useTaskMutation((member: ProjectMember) => taskManagementApi.removeMember(projectId, member.membership_id));
  const userById = new Map(users.map((user) => [user.user_id, user]));
  const available = users.filter((user) => user.status === "Active" && !members.some((member) => member.user_id === user.user_id));
  const changeRole = (member: ProjectMember, next: ProjectMemberRole) => { if (member.role === "MANAGER" && next !== "MANAGER") setConfirm({ member, next }); else void update.mutateAsync({ member, next }).catch((cause) => setError(cause instanceof Error ? cause.message : "Could not change role.")); };
  const runConfirm = async () => { if (!confirm) return; try { if (confirm.next) await update.mutateAsync({ member: confirm.member, next: confirm.next }); else await remove.mutateAsync(confirm.member); setConfirm(null); } catch (cause) { setError(cause instanceof Error ? cause.message : "Could not update membership."); } };
  return <section className={styles.panel}><div className={styles.panelHeader}><div><h2>Project members</h2><p>Roles govern planning, collaboration and read-only access.</p></div></div>{mayManage && <form className={styles.memberForm} onSubmit={(event) => { event.preventDefault(); setError(null); void add.mutateAsync().then(() => setUserId("")).catch((cause) => setError(cause instanceof Error ? cause.message : "Could not add member.")); }}><Field label="User"><select value={userId} onChange={(event) => setUserId(event.target.value)} required><option value="">Select active user</option>{available.map((user) => <option key={user.user_id} value={user.user_id}>{user.name} · {user.role}</option>)}</select></Field><Field label="Project role"><select value={role} onChange={(event) => setRole(event.target.value as ProjectMemberRole)}>{MEMBER_ROLES.map((item) => <option key={item} value={item} disabled={item === "MANAGER" && userById.get(userId)?.role === "Employee"}>{item}</option>)}</select></Field><Button type="submit" className={styles.compactButton} disabled={!userId} loading={add.isPending}><UserPlus size={14} /> Add member</Button></form>}{error && <div className={styles.inlineAlert} role="alert">{error}</div>}
    <div className={styles.memberList}>{members.map((member) => { const user = userById.get(member.user_id); return <article key={member.membership_id}><UserAvatar user={user} size="medium" /><div><strong>{user?.name ?? "Unknown user"}</strong><span>{user?.email ?? member.user_id} · {user?.status ?? "Historical"}</span></div>{mayManage ? <select aria-label={`Role for ${user?.name ?? member.user_id}`} value={member.role} onChange={(event) => changeRole(member, event.target.value as ProjectMemberRole)}>{MEMBER_ROLES.map((item) => <option key={item} disabled={item === "MANAGER" && user?.role === "Employee"}>{item}</option>)}</select> : <span className={styles.memberRole}>{member.role}</span>}{mayManage && <Button type="button" variant="ghost" className={styles.compactButton} onClick={() => setConfirm({ member })}>Remove</Button>}</article>; })}</div>
    <ConfirmDialog open={Boolean(confirm)} title={confirm?.next ? "Downgrade manager role?" : "Remove this project member?"} description={confirm?.next ? "They will immediately lose manager-level project controls." : "Historical comments, time entries and activity remain intact."} confirmLabel={confirm?.next ? "Change role" : "Remove member"} destructive busy={update.isPending || remove.isPending} onCancel={() => setConfirm(null)} onConfirm={() => void runConfirm()} />
  </section>;
};

const ProjectSettings = ({ project }: { project: NonNullable<ReturnType<typeof useProject>["data"]> }) => {
  const [archiveConfirm, setArchiveConfirm] = useState(false); const archive = useTaskMutation(() => taskManagementApi.setProjectArchived(project, !project.archived_at));
  return <div className={styles.settingsGrid}><section className={styles.panel}><div className={styles.panelHeader}><div><h2>Project details</h2><p>Updates use optimistic version checks.</p></div></div><div className={styles.settingsBody}><ProjectForm project={project} onCancel={() => undefined} onSaved={() => undefined} /></div></section><section className={`${styles.panel} ${styles.dangerZone}`}><div className={styles.panelHeader}><div><h2>{project.archived_at ? "Restore project" : "Archive project"}</h2><p>{project.archived_at ? "Return this project to active work." : "Make the workspace read-only without deleting history."}</p></div></div><div className={styles.settingsBody}><Button type="button" variant="secondary" className={styles.compactButton} onClick={() => setArchiveConfirm(true)}>{project.archived_at ? <RotateCcw size={14} /> : <Archive size={14} />}{project.archived_at ? "Restore project" : "Archive project"}</Button></div></section><ConfirmDialog open={archiveConfirm} title={project.archived_at ? "Restore this project?" : "Archive this project?"} description={project.archived_at ? "Project members can resume work after restoration." : "Tasks and collaboration history remain available in read-only mode."} confirmLabel={project.archived_at ? "Restore project" : "Archive project"} destructive={!project.archived_at} busy={archive.isPending} onCancel={() => setArchiveConfirm(false)} onConfirm={() => void archive.mutateAsync().then(() => setArchiveConfirm(false))} /></div>;
};
