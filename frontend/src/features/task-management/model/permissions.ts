import type { TenantRole } from "../../../entities/session/model/session";
import type { ProjectMemberRole, Task } from "./types";

export interface TaskManagementAccess {
  tenantRole: TenantRole;
  memberRole?: ProjectMemberRole | null;
  principalId: string;
}

export const canCreateProject = (role: TenantRole) =>
  role === "Tenant Admin" || role === "Project Manager";

export const canManageProject = ({ tenantRole, memberRole }: TaskManagementAccess) =>
  tenantRole === "Tenant Admin" || memberRole === "MANAGER";

export const canCreateTask = (access: TaskManagementAccess) =>
  canManageProject(access) || access.memberRole === "MEMBER";

export const canCollaborate = (access: TaskManagementAccess) =>
  canManageProject(access) || access.memberRole === "MEMBER";

export const canExecuteTask = (access: TaskManagementAccess, task: Task) =>
  canManageProject(access) || task.assignee_id === access.principalId;
