import { Archive, RotateCcw } from "lucide-react";

import { Button } from "../../../../shared/ui/Button/Button";
import { formatDate, formatHours } from "../../model/format";
import type { Project, Task, UserSummary } from "../../model/types";
import { EmptyState, Pagination, PriorityBadge, StatusBadge, TypeBadge, UserAvatar } from "../primitives";
import styles from "../task-management.module.css";

export const TaskTable = ({ tasks, total, page, pageSize, projects, users, filtered, onOpen, onPageChange, onArchive }: {
  tasks: Task[];
  total: number;
  page: number;
  pageSize: number;
  projects: Project[];
  users: UserSummary[];
  filtered?: boolean;
  onOpen: (task: Task) => void;
  onPageChange: (page: number) => void;
  onArchive?: (task: Task, archived: boolean) => void;
}) => {
  const projectById = new Map(projects.map((project) => [project.project_id, project]));
  const userById = new Map(users.map((user) => [user.user_id, user]));
  if (!tasks.length) return <EmptyState title={filtered ? "No tasks match these filters" : "No tasks yet"} description={filtered ? "Adjust or clear filters to see more work." : "Create a task to begin planning work."} />;
  return (
    <>
      <div className={styles.tableWrap}>
        <table className={styles.table}>
          <thead><tr><th>Key</th><th>Type</th><th>Summary</th><th>Status</th><th>Priority</th><th>Project</th><th>Assignee</th><th>Due</th><th>Estimate</th><th>Actual</th>{onArchive && <th aria-label="Actions" />}</tr></thead>
          <tbody>{tasks.map((task) => {
            const project = projectById.get(task.project_id);
            const assignee = task.assignee_id ? userById.get(task.assignee_id) : undefined;
            return <tr key={task.task_id}>
              <td><button type="button" className={styles.linkButton} onClick={() => onOpen(task)}>{task.display_key}</button></td>
              <td><TypeBadge value={task.task_type} /></td>
              <td><button type="button" className={styles.linkButton} onClick={() => onOpen(task)}>{task.name}</button>{task.archived_at && <span className={styles.archivedNote}>Archived</span>}</td>
              <td><StatusBadge value={task.status} /></td>
              <td><PriorityBadge value={task.priority} /></td>
              <td>{project ? `${project.project_key} · ${project.name}` : "—"}</td>
              <td><span className={styles.userCell}><UserAvatar user={assignee} />{assignee?.name ?? "Unassigned"}</span></td>
              <td>{formatDate(task.end_date)}</td><td>{formatHours(task.estimated_hours)}</td><td>{formatHours(task.actual_hours)}</td>
              {onArchive && <td><div className={styles.rowActions}><Button type="button" variant="ghost" title={task.archived_at ? "Restore task" : "Archive task"} aria-label={task.archived_at ? `Restore ${task.display_key}` : `Archive ${task.display_key}`} onClick={() => onArchive(task, !task.archived_at)}>{task.archived_at ? <RotateCcw size={14} /> : <Archive size={14} />}</Button></div></td>}
            </tr>;
          })}</tbody>
        </table>
      </div>
      <Pagination page={page} pageSize={pageSize} total={total} onPageChange={onPageChange} />
    </>
  );
};

