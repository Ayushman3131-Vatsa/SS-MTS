import type { TaskStatus } from "./types";

export const TASK_TRANSITIONS: Record<TaskStatus, readonly TaskStatus[]> = {
  New: ["Assigned", "In Progress", "Cancelled"],
  Assigned: ["In Progress", "Blocked", "On Hold", "Cancelled"],
  "In Progress": ["Blocked", "On Hold", "Under Review", "Completed", "Cancelled"],
  Blocked: ["In Progress", "On Hold", "Cancelled"],
  "On Hold": ["Assigned", "In Progress", "Cancelled"],
  "Under Review": ["In Progress", "Blocked", "Completed"],
  Completed: ["In Progress"],
  Cancelled: ["New"],
};

export const TERMINAL_STATUSES: readonly TaskStatus[] = ["Completed", "Cancelled"];
export const DEFAULT_PAGE_SIZE = 25;
export const MAX_ATTACHMENT_BYTES = 10 * 1024 * 1024;
export const ATTACHMENT_ACCEPT = [
  "image/png",
  "image/jpeg",
  "image/webp",
  "application/pdf",
  "text/plain",
  "text/csv",
  "application/msword",
  "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
  "application/vnd.ms-excel",
  "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
].join(",");
