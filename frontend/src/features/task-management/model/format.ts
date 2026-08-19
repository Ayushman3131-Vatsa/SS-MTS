export const formatDate = (value: string | null | undefined, withTime = false) => {
  if (!value) return "—";
  const date = new Date(value.length === 10 ? `${value}T00:00:00` : value);
  if (Number.isNaN(date.valueOf())) return value;
  return new Intl.DateTimeFormat(undefined, withTime ? { dateStyle: "medium", timeStyle: "short" } : { dateStyle: "medium" }).format(date);
};

export const formatHours = (value: number) => `${Number(value).toFixed(value % 1 ? 1 : 0)}h`;

export const formatBytes = (value: number) => {
  if (value < 1024) return `${value} B`;
  if (value < 1024 * 1024) return `${(value / 1024).toFixed(1)} KiB`;
  return `${(value / 1024 / 1024).toFixed(1)} MiB`;
};

export const activityLabel = (eventType: string) => {
  const known: Record<string, string> = {
    TASK_CREATED: "created the task",
    TASK_UPDATED: "updated task details",
    STATUS_CHANGED: "changed the status",
    TASK_ARCHIVED: "archived the task",
    TASK_RESTORED: "restored the task",
    COMMENT_ADDED: "added a comment",
    COMMENT_UPDATED: "edited a comment",
    COMMENT_DELETED: "deleted a comment",
    TIME_ENTRY_ADDED: "logged time",
    TIME_ENTRY_UPDATED: "updated a time entry",
    TIME_ENTRY_DELETED: "deleted a time entry",
    ATTACHMENT_ADDED: "attached a file",
    ATTACHMENT_DELETED: "deleted an attachment",
    LINK_ADDED: "linked another task",
    LINK_REMOVED: "removed a task link",
  };
  return known[eventType] ?? eventType.toLowerCase().replaceAll("_", " ");
};

