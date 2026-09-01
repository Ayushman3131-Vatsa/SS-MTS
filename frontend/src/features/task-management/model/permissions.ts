import { pageAccessLevel } from "../../../entities/session/model/page-access";
import type { SessionPrincipal, TenantPrincipal, TenantRole } from "../../../entities/session/model/session";
import type { ProjectMemberRole, Task } from "./types";

export interface TaskManagementAccess {
  tenantRole: TenantRole;
  memberRole?: ProjectMemberRole | null;
  principalId: string;
  hasTenantTaskView: boolean;
  hasTenantTaskModify: boolean;
}

const TASK_MANAGEMENT_ROUTES = [
  "/app/task-management",
  "/app/task-management/projects",
  "/app/task-management/my-work",
  "/app/task-management/tasks",
] as const;

const taskManagementAccessLevel = (
  principal: SessionPrincipal | null | undefined,
): "none" | "view" | "modify" => {
  if (!principal || principal.principal_type !== "tenant_user") {
    return "none";
  }
  if (principal.role === "Tenant Admin") {
    return "modify";
  }
  let level: "none" | "view" | "modify" = "none";
  for (const route of TASK_MANAGEMENT_ROUTES) {
    const grant = pageAccessLevel(principal, route);
    if (grant === "modify") {
      return "modify";
    }
    if (grant === "view") {
      level = "view";
    }
  }
  return level;
};

export const hasTaskManagementView = (
  principal: SessionPrincipal | null | undefined,
): boolean => taskManagementAccessLevel(principal) !== "none";

export const hasTaskManagementModify = (
  principal: SessionPrincipal | null | undefined,
): boolean => taskManagementAccessLevel(principal) === "modify";

export const canCreateProject = (principal: SessionPrincipal | null | undefined) =>
  principal?.principal_type === "tenant_user" && hasTaskManagementModify(principal);

export const buildTaskManagementAccess = (
  principal: TenantPrincipal,
  memberRole?: ProjectMemberRole | null,
): TaskManagementAccess => {
  const level = taskManagementAccessLevel(principal);
  return {
    tenantRole: principal.role,
    memberRole,
    principalId: principal.principal_id,
    hasTenantTaskView: level !== "none",
    hasTenantTaskModify: level === "modify",
  };
};

export const canManageProject = (access: TaskManagementAccess) =>
  access.tenantRole === "Tenant Admin" ||
  access.hasTenantTaskModify ||
  access.memberRole === "MANAGER";

export const canCreateTask = (access: TaskManagementAccess) =>
  canManageProject(access) || access.memberRole === "MEMBER";

export const canCollaborate = (access: TaskManagementAccess) =>
  canManageProject(access) || access.memberRole === "MEMBER";

export const canExecuteTask = (access: TaskManagementAccess, task: Task) =>
  canManageProject(access) || task.assignee_id === access.principalId;
