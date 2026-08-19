import { useMutation, useQuery, useQueryClient, type UseMutationResult } from "@tanstack/react-query";

import { useSession } from "../../../entities/session/model/session-context";
import { taskManagementApi } from "../api/task-management-api";
import type { ProjectFilters, TaskFilters } from "./types";
import { taskManagementKeys } from "./query-keys";
import { announceTaskToast } from "./toast";

export const useTaskTenantId = () => {
  const { principal } = useSession();
  return principal?.principal_type === "tenant_user" ? principal.tenant.tenant_id : "";
};

export const useUsers = () => {
  const tenantId = useTaskTenantId();
  return useQuery({ queryKey: taskManagementKeys.users(tenantId), queryFn: ({ signal }) => taskManagementApi.users(signal), enabled: Boolean(tenantId), staleTime: 60_000 });
};

export const useProjects = (filters: ProjectFilters = {}) => {
  const tenantId = useTaskTenantId();
  return useQuery({ queryKey: taskManagementKeys.projects(tenantId, filters), queryFn: ({ signal }) => taskManagementApi.projects(filters, signal), enabled: Boolean(tenantId), placeholderData: (previous) => previous });
};

export const useProject = (projectId?: string) => {
  const tenantId = useTaskTenantId();
  return useQuery({ queryKey: taskManagementKeys.project(tenantId, projectId ?? ""), queryFn: ({ signal }) => taskManagementApi.project(projectId!, signal), enabled: Boolean(tenantId && projectId) });
};

export const useMembers = (projectId?: string) => {
  const tenantId = useTaskTenantId();
  return useQuery({ queryKey: taskManagementKeys.members(tenantId, projectId ?? ""), queryFn: ({ signal }) => taskManagementApi.members(projectId!, signal), enabled: Boolean(tenantId && projectId) });
};

export const useTasks = (filters: TaskFilters = {}) => {
  const tenantId = useTaskTenantId();
  return useQuery({ queryKey: taskManagementKeys.tasks(tenantId, filters), queryFn: ({ signal }) => taskManagementApi.tasks(filters, signal), enabled: Boolean(tenantId), placeholderData: (previous) => previous });
};

export const useTask = (taskId?: string) => {
  const tenantId = useTaskTenantId();
  return useQuery({ queryKey: taskManagementKeys.task(tenantId, taskId ?? ""), queryFn: ({ signal }) => taskManagementApi.task(taskId!, signal), enabled: Boolean(tenantId && taskId) });
};

export function useTaskMutation<TResult>(mutationFn: () => Promise<TResult>): UseMutationResult<TResult, Error, void>;
export function useTaskMutation<TVariables, TResult>(mutationFn: (variables: TVariables) => Promise<TResult>): UseMutationResult<TResult, Error, TVariables>;
export function useTaskMutation<TVariables, TResult>(mutationFn: (variables: TVariables) => Promise<TResult>) {
  const tenantId = useTaskTenantId();
  const client = useQueryClient();
  return useMutation<TResult, Error, TVariables>({
    mutationFn: (variables) => mutationFn(variables),
    onSuccess: async () => {
      await client.invalidateQueries({ queryKey: taskManagementKeys.root(tenantId) });
      announceTaskToast("Changes saved.");
    },
  });
}
