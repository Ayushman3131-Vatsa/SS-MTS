import { z } from "zod";

import {
  LINK_TYPES,
  MEMBER_ROLES,
  PRIORITIES,
  PROJECT_STATUSES,
  TASK_STATUSES,
  TASK_TYPES,
} from "./types";

const id = z.string().uuid();
const nullableId = id.nullable();
const date = z.string().nullable();
const decimal = z.coerce.number().finite();

export const projectSchema = z.object({
  tenant_id: id,
  project_id: id,
  project_key: z.string(),
  name: z.string(),
  client_name: z.string().nullable(),
  description: z.string().nullable(),
  start_date: date,
  expected_end_date: date,
  status: z.enum(PROJECT_STATUSES),
  priority: z.enum(PRIORITIES),
  pm_id: nullableId,
  dm_id: nullableId,
  remarks: z.string().nullable(),
  version: z.number().int().positive(),
  created_at: z.string(),
  updated_at: z.string(),
  archived_at: z.string().nullable(),
});

export const projectMemberSchema = z.object({
  membership_id: id,
  tenant_id: id,
  project_id: id,
  user_id: id,
  role: z.enum(MEMBER_ROLES),
  added_by_user_id: nullableId,
  created_at: z.string(),
  updated_at: z.string(),
});

export const taskSchema = z.object({
  tenant_id: id,
  task_id: id,
  project_id: id,
  task_number: z.number().int().positive(),
  display_key: z.string(),
  task_type: z.enum(TASK_TYPES),
  parent_task_id: nullableId,
  name: z.string(),
  description: z.string().nullable(),
  task_category: z.string().nullable(),
  assignee_id: nullableId,
  technical_lead_id: nullableId,
  functional_lead_id: nullableId,
  reporter_id: nullableId,
  created_by_user_id: nullableId,
  start_date: date,
  end_date: date,
  estimated_hours: decimal,
  actual_hours: decimal,
  priority: z.enum(PRIORITIES),
  status: z.enum(TASK_STATUSES),
  blocked_by_id: nullableId,
  remarks: z.string().nullable(),
  version: z.number().int().positive(),
  created_at: z.string(),
  updated_at: z.string(),
  completed_at: z.string().nullable(),
  archived_at: z.string().nullable(),
});

export const taskLinkSchema = z.object({
  link_id: id,
  source_task_id: id,
  target_task_id: id,
  link_type: z.enum(LINK_TYPES),
  created_by_user_id: id,
  created_at: z.string(),
});

export const commentSchema = z.object({
  comment_id: id,
  task_id: id,
  commented_by_user_id: id,
  comment_text: z.string(),
  version: z.number().int().positive(),
  created_at: z.string(),
  updated_at: z.string(),
  deleted_at: z.string().nullable(),
});

export const timeEntrySchema = z.object({
  log_id: id,
  task_id: id,
  updated_by_user_id: id,
  hours_worked: decimal,
  work_date: z.string(),
  progress_notes: z.string().nullable(),
  version: z.number().int().positive(),
  log_date: z.string(),
  updated_at: z.string(),
  deleted_at: z.string().nullable(),
});

export const attachmentSchema = z.object({
  attachment_id: id,
  task_id: id,
  original_filename: z.string(),
  media_type: z.string(),
  size_bytes: z.number().int().nonnegative(),
  uploaded_by_user_id: id,
  created_at: z.string(),
});

export const activitySchema = z.object({
  event_id: id,
  task_id: id,
  event_type: z.string(),
  actor_user_id: nullableId,
  data: z.record(z.unknown()),
  occurred_at: z.string(),
});

export const userSummarySchema = z.object({
  tenant_id: id,
  user_id: id,
  name: z.string(),
  username: z.string().optional(),
  email: z.string(),
  role: z.string(),
  status: z.string(),
  version: z.number().int().positive(),
  created_by_user_id: nullableId,
  created_at: z.string(),
});

export const pageSchema = <T extends z.ZodTypeAny>(item: T) =>
  z.object({
    items: z.array(item),
    page: z.number().int().positive(),
    page_size: z.number().int().positive(),
    total: z.number().int().nonnegative(),
  });
