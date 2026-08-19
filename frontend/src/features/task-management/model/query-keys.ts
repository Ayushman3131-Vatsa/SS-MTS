import type { ProjectFilters, TaskFilters } from "./types";

export const taskManagementKeys = {
  root: (tenantId: string) => ["task-management", tenantId] as const,
  users: (tenantId: string) => [...taskManagementKeys.root(tenantId), "users"] as const,
  projects: (tenantId: string, filters: ProjectFilters) => [...taskManagementKeys.root(tenantId), "projects", filters] as const,
  project: (tenantId: string, projectId: string) => [...taskManagementKeys.root(tenantId), "project", projectId] as const,
  members: (tenantId: string, projectId: string) => [...taskManagementKeys.project(tenantId, projectId), "members"] as const,
  tasks: (tenantId: string, filters: TaskFilters) => [...taskManagementKeys.root(tenantId), "tasks", filters] as const,
  task: (tenantId: string, taskId: string) => [...taskManagementKeys.root(tenantId), "task", taskId] as const,
  comments: (tenantId: string, taskId: string) => [...taskManagementKeys.task(tenantId, taskId), "comments"] as const,
  time: (tenantId: string, taskId: string) => [...taskManagementKeys.task(tenantId, taskId), "time"] as const,
  attachments: (tenantId: string, taskId: string) => [...taskManagementKeys.task(tenantId, taskId), "attachments"] as const,
  links: (tenantId: string, taskId: string) => [...taskManagementKeys.task(tenantId, taskId), "links"] as const,
  activity: (tenantId: string, taskId: string) => [...taskManagementKeys.task(tenantId, taskId), "activity"] as const,
};

