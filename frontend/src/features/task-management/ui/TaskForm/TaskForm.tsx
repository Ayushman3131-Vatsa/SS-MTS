import { zodResolver } from "@hookform/resolvers/zod";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";

import { ApiError } from "../../../../shared/api/errors";
import { Button } from "../../../../shared/ui/Button/Button";
import { ConfirmDialog } from "../../../../shared/ui/ConfirmDialog/ConfirmDialog";
import { taskManagementApi } from "../../api/task-management-api";
import { PRIORITIES, TASK_TYPES, type Task, type UserSummary } from "../../model/types";
import { useTaskMutation, useTasks } from "../../model/use-task-management";
import { Field } from "../primitives";
import styles from "../task-management.module.css";

const schema = z.object({
  name: z.string().trim().min(1, "Summary is required.").max(255),
  task_type: z.enum(TASK_TYPES),
  parent_task_id: z.string().optional(),
  description: z.string().trim().max(50_000).optional(),
  task_category: z.string().trim().max(100).optional(),
  assignee_id: z.string().optional(),
  technical_lead_id: z.string().optional(),
  functional_lead_id: z.string().optional(),
  start_date: z.string().optional(),
  end_date: z.string().optional(),
  estimated_hours: z.coerce.number().min(0).max(99_999_999),
  priority: z.enum(PRIORITIES),
  blocked_by_id: z.string().optional(),
  remarks: z.string().trim().max(20_000).optional(),
}).refine((data) => !data.start_date || !data.end_date || data.end_date >= data.start_date, { path: ["end_date"], message: "End date must be on or after the start date." });

type Values = z.infer<typeof schema>;

export const TaskForm = ({ projectId, users, managerFields, onSaved, onCancel }: { projectId: string; users: UserSummary[]; managerFields: boolean; onSaved: (task: Task) => void; onCancel: () => void }) => {
  const [candidateQuery, setCandidateQuery] = useState("");
  const [confirmClose, setConfirmClose] = useState(false);
  const candidates = useTasks({ project_id: projectId, query: candidateQuery, page_size: 100, sort: "task_number" });
  const { register, watch, handleSubmit, setError, formState: { errors, isDirty } } = useForm<Values>({
    resolver: zodResolver(schema),
    defaultValues: { name: "", task_type: "TASK", parent_task_id: "", description: "", task_category: "", assignee_id: "", technical_lead_id: "", functional_lead_id: "", start_date: "", end_date: "", estimated_hours: 0, priority: "Medium", blocked_by_id: "", remarks: "" },
  });
  const taskType = watch("task_type");
  const mutation = useTaskMutation((values: Values) => taskManagementApi.createTask(projectId, {
    ...values,
    parent_task_id: values.parent_task_id || null,
    description: values.description || null,
    task_category: values.task_category || null,
    assignee_id: managerFields ? values.assignee_id || null : null,
    technical_lead_id: managerFields ? values.technical_lead_id || null : null,
    functional_lead_id: managerFields ? values.functional_lead_id || null : null,
    start_date: values.start_date || null,
    end_date: values.end_date || null,
    blocked_by_id: values.blocked_by_id || null,
    remarks: values.remarks || null,
  }));
  const activeUsers = users.filter((user) => user.status === "Active");
  const parentCandidates = (candidates.data?.items ?? []).filter((task) => taskType === "SUBTASK" ? ["STORY", "TASK", "BUG"].includes(task.task_type) : task.task_type === "EPIC");

  const submit = handleSubmit(async (values) => {
    try { onSaved(await mutation.mutateAsync(values)); }
    catch (error) { setError("root", { message: error instanceof ApiError && error.status === 409 ? "Task data is out of date. Your draft is preserved; reload and try again." : error instanceof Error ? error.message : "Could not create the task." }); }
  });

  return (
    <form className={styles.formGrid} onSubmit={submit}>
      <div className={styles.span2}><Field label="Summary" error={errors.name?.message}><input {...register("name")} autoFocus placeholder="What needs to be done?" /></Field></div>
      <Field label="Type" error={errors.task_type?.message}><select {...register("task_type")}><option value="EPIC">Epic</option><option value="STORY">Story</option><option value="TASK">Task</option><option value="BUG">Bug</option><option value="SUBTASK">Subtask</option></select></Field>
      <Field label="Priority" error={errors.priority?.message}><select {...register("priority")}>{PRIORITIES.map((value) => <option key={value}>{value}</option>)}</select></Field>
      {taskType !== "EPIC" && <div className={styles.span2}><Field label="Parent"><input value={candidateQuery} onChange={(event) => setCandidateQuery(event.target.value)} placeholder="Search parent candidates" /><select {...register("parent_task_id")}><option value="">No parent</option>{parentCandidates.map((task) => <option key={task.task_id} value={task.task_id}>{task.display_key} · {task.name}</option>)}</select></Field></div>}
      {managerFields && <Field label="Assignee"><select {...register("assignee_id")}><option value="">Unassigned</option>{activeUsers.map((user) => <option key={user.user_id} value={user.user_id}>{user.name}</option>)}</select></Field>}
      <Field label="Category" error={errors.task_category?.message}><input {...register("task_category")} placeholder="Optional category" /></Field>
      {managerFields && <><Field label="Technical lead"><select {...register("technical_lead_id")}><option value="">None</option>{activeUsers.map((user) => <option key={user.user_id} value={user.user_id}>{user.name}</option>)}</select></Field><Field label="Functional lead"><select {...register("functional_lead_id")}><option value="">None</option>{activeUsers.map((user) => <option key={user.user_id} value={user.user_id}>{user.name}</option>)}</select></Field></>}
      <Field label="Start date"><input type="date" {...register("start_date")} /></Field>
      <Field label="Due date" error={errors.end_date?.message}><input type="date" {...register("end_date")} /></Field>
      <Field label="Estimate (hours)" error={errors.estimated_hours?.message}><input type="number" min="0" step="0.25" {...register("estimated_hours")} /></Field>
      <Field label="Blocked by"><select {...register("blocked_by_id")}><option value="">Not blocked by a task</option>{(candidates.data?.items ?? []).map((task) => <option key={task.task_id} value={task.task_id}>{task.display_key} · {task.name}</option>)}</select></Field>
      <div className={styles.span2}><Field label="Description"><textarea {...register("description")} placeholder="Acceptance criteria, context and details" /></Field></div>
      <div className={styles.span2}><Field label="Remarks"><textarea {...register("remarks")} placeholder="Internal notes" /></Field></div>
      {errors.root?.message && <div className={`${styles.inlineAlert} ${styles.span2}`} role="alert">{errors.root.message}</div>}
      <div className={styles.formActions}><Button type="button" variant="secondary" onClick={() => isDirty ? setConfirmClose(true) : onCancel()}>Cancel{isDirty ? " changes" : ""}</Button><Button type="submit" loading={mutation.isPending} loadingLabel="Creating…">Create task</Button></div>
      <ConfirmDialog open={confirmClose} title="Discard unsaved changes?" description="Your task draft has not been saved." confirmLabel="Discard changes" destructive onCancel={() => setConfirmClose(false)} onConfirm={onCancel} />
    </form>
  );
};
