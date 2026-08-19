import { z } from "zod";

import { apiDownload, apiRequest } from "../../../shared/api/client";
import { InvalidApiResponseError } from "../../../shared/api/errors";
import {
  activitySchema,
  attachmentSchema,
  commentSchema,
  pageSchema,
  projectMemberSchema,
  projectSchema,
  taskLinkSchema,
  taskSchema,
  timeEntrySchema,
  userSummarySchema,
} from "../model/schemas";
import type {
  Page,
  Project,
  ProjectFilters,
  ProjectInput,
  ProjectMember,
  ProjectMemberRole,
  Task,
  TaskFilters,
  TaskInput,
  TaskLinkType,
} from "../model/types";

const ROOT = "/task-management";

const parse = <T>(schema: z.ZodType<T>, value: unknown): T => {
  const result = schema.safeParse(value);
  if (!result.success) throw new InvalidApiResponseError();
  return result.data;
};

const queryString = (values: object) => {
  const query = new URLSearchParams();
  Object.entries(values).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== "") {
      query.set(key, String(value));
    }
  });
  const encoded = query.toString();
  return encoded ? `?${encoded}` : "";
};

const requestAndParse = async <T>(
  path: string,
  schema: z.ZodType<T>,
  options?: Parameters<typeof apiRequest>[1],
) => parse(schema, await apiRequest<unknown>(path, options));

export const taskManagementApi = {
  projects: (filters: ProjectFilters = {}, signal?: AbortSignal): Promise<Page<Project>> =>
    requestAndParse(`${ROOT}/projects${queryString(filters)}`, pageSchema(projectSchema), { signal }),

  project: (projectId: string, signal?: AbortSignal) =>
    requestAndParse(`${ROOT}/projects/${projectId}`, projectSchema, { signal }),

  createProject: (input: ProjectInput) =>
    requestAndParse(`${ROOT}/projects`, projectSchema, { method: "POST", body: input }),

  updateProject: (projectId: string, input: Partial<ProjectInput> & { version: number }) =>
    requestAndParse(`${ROOT}/projects/${projectId}`, projectSchema, { method: "PATCH", body: input }),

  setProjectArchived: (project: Project, archived: boolean) =>
    requestAndParse(`${ROOT}/projects/${project.project_id}/${archived ? "archive" : "restore"}`, projectSchema, {
      method: "POST",
      body: { version: project.version },
    }),

  members: (projectId: string, signal?: AbortSignal): Promise<Page<ProjectMember>> =>
    requestAndParse(`${ROOT}/projects/${projectId}/members?page=1&page_size=100`, pageSchema(projectMemberSchema), { signal }),

  addMember: (projectId: string, userId: string, role: ProjectMemberRole) =>
    requestAndParse(`${ROOT}/projects/${projectId}/members`, projectMemberSchema, {
      method: "POST",
      body: { user_id: userId, role },
    }),

  updateMember: (projectId: string, membershipId: string, role: ProjectMemberRole) =>
    requestAndParse(`${ROOT}/projects/${projectId}/members/${membershipId}`, projectMemberSchema, {
      method: "PATCH",
      body: { role },
    }),

  removeMember: (projectId: string, membershipId: string) =>
    apiRequest<void>(`${ROOT}/projects/${projectId}/members/${membershipId}`, { method: "DELETE" }),

  tasks: (filters: TaskFilters = {}, signal?: AbortSignal): Promise<Page<Task>> =>
    requestAndParse(`${ROOT}/tasks${queryString(filters)}`, pageSchema(taskSchema), { signal }),

  task: (taskId: string, signal?: AbortSignal) =>
    requestAndParse(`${ROOT}/tasks/${taskId}`, taskSchema, { signal }),

  createTask: (projectId: string, input: TaskInput) =>
    requestAndParse(`${ROOT}/projects/${projectId}/tasks`, taskSchema, { method: "POST", body: input }),

  updateTask: (taskId: string, input: Partial<Omit<TaskInput, "status">> & { version: number }) =>
    requestAndParse(`${ROOT}/tasks/${taskId}`, taskSchema, { method: "PATCH", body: input }),

  transitionTask: (taskId: string, toStatus: Task["status"], version: number, reason?: string) =>
    requestAndParse(`${ROOT}/tasks/${taskId}/transitions`, taskSchema, {
      method: "POST",
      body: { to_status: toStatus, version, reason: reason || null },
    }),

  setTaskArchived: (task: Task, archived: boolean) =>
    requestAndParse(`${ROOT}/tasks/${task.task_id}/${archived ? "archive" : "restore"}`, taskSchema, {
      method: "POST",
      body: { version: task.version },
    }),

  users: (signal?: AbortSignal) =>
    requestAndParse("/users", z.array(userSummarySchema), { signal }),

  comments: (taskId: string, signal?: AbortSignal) =>
    requestAndParse(`${ROOT}/tasks/${taskId}/comments?page=1&page_size=100`, pageSchema(commentSchema), { signal }),
  createComment: (taskId: string, commentText: string) =>
    requestAndParse(`${ROOT}/tasks/${taskId}/comments`, commentSchema, { method: "POST", body: { comment_text: commentText } }),
  updateComment: (taskId: string, commentId: string, commentText: string, version: number) =>
    requestAndParse(`${ROOT}/tasks/${taskId}/comments/${commentId}`, commentSchema, { method: "PATCH", body: { comment_text: commentText, version } }),
  deleteComment: (taskId: string, commentId: string, version: number) =>
    apiRequest<void>(`${ROOT}/tasks/${taskId}/comments/${commentId}`, { method: "DELETE", body: { version } }),

  timeEntries: (taskId: string, signal?: AbortSignal) =>
    requestAndParse(`${ROOT}/tasks/${taskId}/time-entries?page=1&page_size=100`, pageSchema(timeEntrySchema), { signal }),
  createTimeEntry: (taskId: string, input: { hours_worked: number; work_date: string; progress_notes?: string | null }) =>
    requestAndParse(`${ROOT}/tasks/${taskId}/time-entries`, timeEntrySchema, { method: "POST", body: input }),
  updateTimeEntry: (taskId: string, entryId: string, input: { hours_worked: number; work_date: string; progress_notes?: string | null; version: number }) =>
    requestAndParse(`${ROOT}/tasks/${taskId}/time-entries/${entryId}`, timeEntrySchema, { method: "PATCH", body: input }),
  deleteTimeEntry: (taskId: string, entryId: string, version: number) =>
    apiRequest<void>(`${ROOT}/tasks/${taskId}/time-entries/${entryId}`, { method: "DELETE", body: { version } }),

  attachments: (taskId: string, signal?: AbortSignal) =>
    requestAndParse(`${ROOT}/tasks/${taskId}/attachments?page=1&page_size=100`, pageSchema(attachmentSchema), { signal }),
  uploadAttachment: (taskId: string, file: File) => {
    const body = new FormData();
    body.append("file", file);
    return requestAndParse(`${ROOT}/tasks/${taskId}/attachments`, attachmentSchema, { method: "POST", body });
  },
  downloadAttachment: (taskId: string, attachmentId: string, signal?: AbortSignal) =>
    apiDownload(`${ROOT}/tasks/${taskId}/attachments/${attachmentId}/download`, signal),
  deleteAttachment: (taskId: string, attachmentId: string) =>
    apiRequest<void>(`${ROOT}/tasks/${taskId}/attachments/${attachmentId}`, { method: "DELETE" }),

  links: (taskId: string, signal?: AbortSignal) =>
    requestAndParse(`${ROOT}/tasks/${taskId}/links?page=1&page_size=100`, pageSchema(taskLinkSchema), { signal }),
  createLink: (taskId: string, targetTaskId: string, linkType: TaskLinkType) =>
    requestAndParse(`${ROOT}/tasks/${taskId}/links`, taskLinkSchema, { method: "POST", body: { target_task_id: targetTaskId, link_type: linkType } }),
  deleteLink: (taskId: string, linkId: string) =>
    apiRequest<void>(`${ROOT}/tasks/${taskId}/links/${linkId}`, { method: "DELETE" }),

  activity: (taskId: string, signal?: AbortSignal) =>
    requestAndParse(`${ROOT}/tasks/${taskId}/activity?page=1&page_size=100`, pageSchema(activitySchema), { signal }),
};
