export const TASK_TOAST_EVENT = "task-management:toast";
export const announceTaskToast = (message: string) => window.dispatchEvent(new CustomEvent(TASK_TOAST_EVENT, { detail: { message } }));

