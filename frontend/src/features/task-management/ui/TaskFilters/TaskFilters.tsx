import { RotateCcw, Search } from "lucide-react";
import { useEffect, useState } from "react";

import { Button } from "../../../../shared/ui/Button/Button";
import { useDebouncedValue } from "../../model/use-debounced-value";
import { PRIORITIES, PROJECT_STATUSES, TASK_STATUSES, TASK_TYPES, type Project, type UserSummary } from "../../model/types";
import styles from "../task-management.module.css";

export interface TaskFilterValues {
  query?: string;
  project_id?: string;
  status?: string;
  priority?: string;
  task_type?: string;
  assignee_id?: string;
  reporter_id?: string;
  member_id?: string;
  due_from?: string;
  due_to?: string;
  archived?: string;
  sort?: string;
}

export const TaskFilters = ({ value, projects, users, hideProject = false, hideStatus = false, onChange }: { value: TaskFilterValues; projects: Project[]; users: UserSummary[]; hideProject?: boolean; hideStatus?: boolean; onChange: (value: TaskFilterValues) => void }) => {
  const [search, setSearch] = useState(value.query ?? "");
  const debouncedSearch = useDebouncedValue(search);
  useEffect(() => { if ((value.query ?? "") !== debouncedSearch) onChange({ ...value, query: debouncedSearch || undefined }); }, [debouncedSearch]); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => setSearch(value.query ?? ""), [value.query]);
  const update = (key: keyof TaskFilterValues, next: string) => onChange({ ...value, [key]: next || undefined });
  const hasFilters = Object.entries(value).some(([key, item]) => key !== "sort" && Boolean(item));
  return (
    <div className={styles.toolbar} aria-label="Task filters">
      <label className={styles.search}><span>Search</span><span className={styles.searchInput}><Search size={14} /><input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Key or summary" /></span></label>
      {!hideProject && <label><span>Project</span><select value={value.project_id ?? ""} onChange={(event) => update("project_id", event.target.value)}><option value="">All projects</option>{projects.map((project) => <option key={project.project_id} value={project.project_id}>{project.project_key} · {project.name}</option>)}</select></label>}
      {!hideStatus && <label><span>Status</span><select value={value.status ?? ""} onChange={(event) => update("status", event.target.value)}><option value="">All statuses</option>{TASK_STATUSES.map((item) => <option key={item}>{item}</option>)}</select></label>}
      <label><span>Priority</span><select value={value.priority ?? ""} onChange={(event) => update("priority", event.target.value)}><option value="">All priorities</option>{PRIORITIES.map((item) => <option key={item}>{item}</option>)}</select></label>
      <label><span>Type</span><select value={value.task_type ?? ""} onChange={(event) => update("task_type", event.target.value)}><option value="">All types</option>{TASK_TYPES.map((item) => <option key={item}>{item}</option>)}</select></label>
      <label><span>Assignee</span><select value={value.assignee_id ?? ""} onChange={(event) => update("assignee_id", event.target.value)}><option value="">Anyone</option>{users.map((user) => <option key={user.user_id} value={user.user_id}>{user.name}{user.status !== "Active" ? " (inactive)" : ""}</option>)}</select></label>
      <label><span>Reporter</span><select value={value.reporter_id ?? ""} onChange={(event) => update("reporter_id", event.target.value)}><option value="">Anyone</option>{users.map((user) => <option key={user.user_id} value={user.user_id}>{user.name}</option>)}</select></label>
      <label><span>Member</span><select value={value.member_id ?? ""} onChange={(event) => update("member_id", event.target.value)}><option value="">Any member</option>{users.map((user) => <option key={user.user_id} value={user.user_id}>{user.name}</option>)}</select></label>
      <label><span>Due from</span><input type="date" value={value.due_from ?? ""} onChange={(event) => update("due_from", event.target.value)} /></label>
      <label><span>Due to</span><input type="date" value={value.due_to ?? ""} onChange={(event) => update("due_to", event.target.value)} /></label>
      <label><span>Archive</span><select value={value.archived ?? ""} onChange={(event) => update("archived", event.target.value)}><option value="">Active only</option><option value="true">Archived only</option></select></label>
      <label><span>Sort</span><select value={value.sort ?? "-updated_at"} onChange={(event) => update("sort", event.target.value)}><option value="-updated_at">Recently updated</option><option value="task_number">Task key</option><option value="due_date">Due date</option><option value="-priority">Priority</option></select></label>
      {hasFilters && <Button type="button" variant="ghost" className={styles.compactButton} onClick={() => { setSearch(""); onChange({ sort: value.sort }); }}><RotateCcw size={14} /> Clear</Button>}
    </div>
  );
};

export const ProjectFilters = ({ query, status, archived, sort, onChange }: { query: string; status: string; archived: string; sort: string; onChange: (key: string, value: string) => void }) => (
  <div className={styles.toolbar} aria-label="Project filters">
    <label className={styles.search}><span>Search</span><span className={styles.searchInput}><Search size={14} /><input value={query} onChange={(event) => onChange("query", event.target.value)} placeholder="Project key, name or client" /></span></label>
    <label><span>Status</span><select value={status} onChange={(event) => onChange("status", event.target.value)}><option value="">All statuses</option>{PROJECT_STATUSES.map((item) => <option key={item}>{item}</option>)}</select></label>
    <label><span>Archive</span><select value={archived} onChange={(event) => onChange("archived", event.target.value)}><option value="">Active only</option><option value="true">Include archived</option></select></label>
    <label><span>Sort</span><select value={sort} onChange={(event) => onChange("sort", event.target.value)}><option value="-updated_at">Recently updated</option><option value="project_key">Project key</option><option value="name">Name</option><option value="status">Status</option></select></label>
  </div>
);
