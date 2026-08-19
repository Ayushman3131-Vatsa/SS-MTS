import { ArrowRight, BriefcaseBusiness, CheckCircle2, CircleDot, Plus, UserRoundCheck } from "lucide-react";
import { useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";

import { useSession } from "../../entities/session/model/session-context";
import { canCreateProject } from "../../features/task-management/model/permissions";
import { formatDate } from "../../features/task-management/model/format";
import { useProjects, useTasks, useUsers } from "../../features/task-management/model/use-task-management";
import { Overlay, PageHeading, PriorityBadge, StatusBadge } from "../../features/task-management/ui/primitives";
import { ProjectForm } from "../../features/task-management/ui/ProjectForm/ProjectForm";
import { TaskDrawer } from "../../features/task-management/ui/TaskDrawer/TaskDrawer";
import styles from "../../features/task-management/ui/task-management.module.css";
import { Button } from "../../shared/ui/Button/Button";

export const TaskManagementOverviewPage = () => {
  const { principal } = useSession();
  const navigate = useNavigate();
  const [params, setParams] = useSearchParams();
  const [creatingProject, setCreatingProject] = useState(false);
  const projectQuery = useProjects({ page: 1, page_size: 6, sort: "-updated_at" });
  const recentQuery = useTasks({ page: 1, page_size: 8, sort: "-updated_at" });
  const myQuery = useTasks({ page: 1, page_size: 1, assignee_id: principal?.principal_id });
  const progressQuery = useTasks({ page: 1, page_size: 1, status: "In Progress" });
  const completeQuery = useTasks({ page: 1, page_size: 1, status: "Completed" });
  const users = useUsers();
  if (!principal || principal.principal_type !== "tenant_user") return null;
  const projects = projectQuery.data?.items ?? [];
  const projectById = new Map(projects.map((project) => [project.project_id, project]));
  const userById = new Map((users.data ?? []).map((user) => [user.user_id, user]));
  const selectedTaskId = params.get("task") ?? undefined;
  const closeTask = () => { const next = new URLSearchParams(params); next.delete("task"); setParams(next, { replace: true }); };
  return <div className={styles.content}>
    <PageHeading eyebrow="Task Management" title="Work overview" description="A compact view of delivery health across projects you can access." actions={<><Button type="button" variant="secondary" className={styles.compactButton} onClick={() => navigate("/app/task-management/tasks")}>View all work <ArrowRight size={14} /></Button>{canCreateProject(principal.role) && <Button type="button" className={styles.compactButton} onClick={() => setCreatingProject(true)}><Plus size={14} /> New project</Button>}</>} />
    <section className={styles.kpiGrid} aria-label="Task management summary">
      <article><span className={styles.kpiIcon}><BriefcaseBusiness size={17} /></span><div><small>Accessible projects</small><strong>{projectQuery.data?.total ?? "—"}</strong></div></article>
      <article><span className={styles.kpiIcon}><UserRoundCheck size={17} /></span><div><small>Assigned to me</small><strong>{myQuery.data?.total ?? "—"}</strong></div></article>
      <article><span className={styles.kpiIcon}><CircleDot size={17} /></span><div><small>In progress</small><strong>{progressQuery.data?.total ?? "—"}</strong></div></article>
      <article><span className={styles.kpiIcon}><CheckCircle2 size={17} /></span><div><small>Completed</small><strong>{completeQuery.data?.total ?? "—"}</strong></div></article>
    </section>
    <div className={styles.overviewGrid}>
      <section className={styles.panel}><div className={styles.panelHeader}><div><h2>Recently updated work</h2><p>Latest changes across your accessible projects</p></div></div><div className={styles.tableWrap}><table className={styles.table}><thead><tr><th>Task</th><th>Status</th><th>Priority</th><th>Assignee</th><th>Updated</th></tr></thead><tbody>{(recentQuery.data?.items ?? []).map((task) => <tr key={task.task_id}><td><button type="button" className={styles.linkButton} onClick={() => { const next = new URLSearchParams(params); next.set("task", task.task_id); setParams(next); }}>{task.display_key} · {task.name}</button></td><td><StatusBadge value={task.status} /></td><td><PriorityBadge value={task.priority} /></td><td>{task.assignee_id ? userById.get(task.assignee_id)?.name ?? "Unknown user" : "Unassigned"}</td><td>{formatDate(task.updated_at, true)}</td></tr>)}</tbody></table></div></section>
      <section className={styles.panel}><div className={styles.panelHeader}><div><h2>Project summary</h2><p>Recently active projects</p></div><Button type="button" variant="ghost" className={styles.compactButton} onClick={() => navigate("/app/task-management/projects")}>All projects</Button></div><div className={styles.projectSummary}>{projects.map((project) => <button key={project.project_id} type="button" onClick={() => navigate(`/app/task-management/projects/${project.project_id}/board`)}><span><strong>{project.project_key}</strong><small>{project.name}</small></span><StatusBadge value={project.status} /><ArrowRight size={14} /></button>)}</div></section>
    </div>
    <Overlay open={creatingProject} title="Create project" description="Set up a workspace and its first manager membership." onClose={() => setCreatingProject(false)} wide guardDirtyForm><ProjectForm onCancel={() => setCreatingProject(false)} onSaved={(project) => { setCreatingProject(false); navigate(`/app/task-management/projects/${project.project_id}/board`); }} /></Overlay>
    <TaskDrawer taskId={selectedTaskId} projects={Array.from(projectById.values())} users={users.data ?? []} onClose={closeTask} />
  </div>;
};
