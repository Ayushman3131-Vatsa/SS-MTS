export const PROJECT_STATUSES = [
  "Not Started",
  "In Progress",
  "On Hold",
  "Completed",
  "Cancelled",
] as const;
export type ProjectStatus = (typeof PROJECT_STATUSES)[number];

export const TASK_STATUSES = [
  "New",
  "Assigned",
  "In Progress",
  "Blocked",
  "On Hold",
  "Under Review",
  "Completed",
  "Cancelled",
] as const;
export type TaskStatus = (typeof TASK_STATUSES)[number];

export const PRIORITIES = ["Low", "Medium", "High", "Critical"] as const;
export type Priority = (typeof PRIORITIES)[number];

export const TASK_TYPES = ["EPIC", "STORY", "TASK", "BUG", "SUBTASK"] as const;
export type TaskType = (typeof TASK_TYPES)[number];

export const MEMBER_ROLES = ["MANAGER", "MEMBER", "VIEWER"] as const;
export type ProjectMemberRole = (typeof MEMBER_ROLES)[number];

export const LINK_TYPES = ["BLOCKS", "RELATES_TO", "DUPLICATES"] as const;
export type TaskLinkType = (typeof LINK_TYPES)[number];

export interface Page<T> {
  items: T[];
  page: number;
  page_size: number;
  total: number;
}

export interface UserSummary {
  tenant_id: string;
  user_id: string;
  name: string;
  email: string;
  role: string;
  status: string;
  version: number;
  created_by_user_id: string | null;
  created_at: string;
}

export interface Project {
  tenant_id: string;
  project_id: string;
  project_key: string;
  name: string;
  client_name: string | null;
  description: string | null;
  start_date: string | null;
  expected_end_date: string | null;
  status: ProjectStatus;
  priority: Priority;
  pm_id: string | null;
  dm_id: string | null;
  remarks: string | null;
  version: number;
  created_at: string;
  updated_at: string;
  archived_at: string | null;
}

export interface ProjectMember {
  membership_id: string;
  tenant_id: string;
  project_id: string;
  user_id: string;
  role: ProjectMemberRole;
  added_by_user_id: string | null;
  created_at: string;
  updated_at: string;
}

export interface Task {
  tenant_id: string;
  task_id: string;
  project_id: string;
  task_number: number;
  display_key: string;
  task_type: TaskType;
  parent_task_id: string | null;
  name: string;
  description: string | null;
  task_category: string | null;
  assignee_id: string | null;
  technical_lead_id: string | null;
  functional_lead_id: string | null;
  reporter_id: string | null;
  created_by_user_id: string | null;
  start_date: string | null;
  end_date: string | null;
  estimated_hours: number;
  actual_hours: number;
  priority: Priority;
  status: TaskStatus;
  blocked_by_id: string | null;
  remarks: string | null;
  version: number;
  created_at: string;
  updated_at: string;
  completed_at: string | null;
  archived_at: string | null;
}

export interface TaskLink {
  link_id: string;
  source_task_id: string;
  target_task_id: string;
  link_type: TaskLinkType;
  created_by_user_id: string;
  created_at: string;
}

export interface TaskComment {
  comment_id: string;
  task_id: string;
  commented_by_user_id: string;
  comment_text: string;
  version: number;
  created_at: string;
  updated_at: string;
  deleted_at: string | null;
}

export interface TimeEntry {
  log_id: string;
  task_id: string;
  updated_by_user_id: string;
  hours_worked: number;
  work_date: string;
  progress_notes: string | null;
  version: number;
  log_date: string;
  updated_at: string;
  deleted_at: string | null;
}

export interface TaskAttachment {
  attachment_id: string;
  task_id: string;
  original_filename: string;
  media_type: string;
  size_bytes: number;
  uploaded_by_user_id: string;
  created_at: string;
}

export interface ActivityEvent {
  event_id: string;
  task_id: string;
  event_type: string;
  actor_user_id: string | null;
  data: Record<string, unknown>;
  occurred_at: string;
}

export interface ProjectFilters {
  page?: number;
  page_size?: number;
  query?: string;
  status?: ProjectStatus;
  member_id?: string;
  include_archived?: boolean;
  sort?: string;
}

export interface TaskFilters {
  page?: number;
  page_size?: number;
  project_id?: string;
  query?: string;
  status?: TaskStatus;
  priority?: Priority;
  task_type?: TaskType;
  assignee_id?: string;
  reporter_id?: string;
  member_id?: string;
  due_from?: string;
  due_to?: string;
  archived?: boolean;
  include_archived?: boolean;
  sort?: string;
}

export interface ProjectInput {
  project_key?: string;
  name: string;
  client_name?: string | null;
  description?: string | null;
  start_date?: string | null;
  expected_end_date?: string | null;
  status?: ProjectStatus;
  priority?: Priority;
  pm_id?: string | null;
  dm_id?: string | null;
  remarks?: string | null;
}

export interface TaskInput {
  parent_task_id?: string | null;
  task_type?: TaskType;
  name: string;
  description?: string | null;
  task_category?: string | null;
  assignee_id?: string | null;
  technical_lead_id?: string | null;
  functional_lead_id?: string | null;
  start_date?: string | null;
  end_date?: string | null;
  estimated_hours?: number;
  priority?: Priority;
  status?: TaskStatus;
  blocked_by_id?: string | null;
  remarks?: string | null;
}
