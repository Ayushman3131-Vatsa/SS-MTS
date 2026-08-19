import { zodResolver } from "@hookform/resolvers/zod";
import { useEffect, useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";

import { ApiError } from "../../../../shared/api/errors";
import { Button } from "../../../../shared/ui/Button/Button";
import { ConfirmDialog } from "../../../../shared/ui/ConfirmDialog/ConfirmDialog";
import { taskManagementApi } from "../../api/task-management-api";
import { PRIORITIES, PROJECT_STATUSES, type Project } from "../../model/types";
import { useTaskMutation } from "../../model/use-task-management";
import { Field } from "../primitives";
import styles from "../task-management.module.css";

const schema = z.object({
  project_key: z.string().trim().toUpperCase().regex(/^[A-Z][A-Z0-9]{1,9}$/, "Use 2–10 uppercase letters or numbers.").optional().or(z.literal("")),
  name: z.string().trim().min(1, "Project name is required.").max(255),
  client_name: z.string().trim().max(255).optional(),
  description: z.string().trim().max(50_000).optional(),
  start_date: z.string().optional(),
  expected_end_date: z.string().optional(),
  status: z.enum(PROJECT_STATUSES),
  priority: z.enum(PRIORITIES),
  remarks: z.string().trim().max(20_000).optional(),
}).refine((data) => !data.start_date || !data.expected_end_date || data.expected_end_date >= data.start_date, {
  path: ["expected_end_date"], message: "End date must be on or after the start date.",
});

type Values = z.infer<typeof schema>;

const valuesFor = (project?: Project): Values => ({
  project_key: project?.project_key ?? "",
  name: project?.name ?? "",
  client_name: project?.client_name ?? "",
  description: project?.description ?? "",
  start_date: project?.start_date ?? "",
  expected_end_date: project?.expected_end_date ?? "",
  status: project?.status ?? "Not Started",
  priority: project?.priority ?? "Medium",
  remarks: project?.remarks ?? "",
});

export const ProjectForm = ({ project, onSaved, onCancel }: { project?: Project; onSaved: (project: Project) => void; onCancel: () => void }) => {
  const [confirmClose, setConfirmClose] = useState(false);
  const { register, handleSubmit, reset, setError, formState: { errors, isDirty } } = useForm<Values>({ resolver: zodResolver(schema), defaultValues: valuesFor(project) });
  const mutation = useTaskMutation((values: Values) => {
    const input = {
      ...values,
      project_key: values.project_key || undefined,
      client_name: values.client_name || null,
      description: values.description || null,
      start_date: values.start_date || null,
      expected_end_date: values.expected_end_date || null,
      remarks: values.remarks || null,
    };
    return project
      ? taskManagementApi.updateProject(project.project_id, { ...input, project_key: undefined, version: project.version })
      : taskManagementApi.createProject(input);
  });

  useEffect(() => reset(valuesFor(project)), [project, reset]);

  const submit = handleSubmit(async (values) => {
    try { onSaved(await mutation.mutateAsync(values)); }
    catch (error) {
      setError("root", { message: error instanceof ApiError && error.status === 409 ? "This project changed while you were editing. Your draft is preserved; reload before saving again." : error instanceof Error ? error.message : "Could not save the project." });
    }
  });

  return (
    <form className={styles.formGrid} onSubmit={submit}>
      {!project && <Field label="Project key" error={errors.project_key?.message}><input {...register("project_key")} placeholder="Auto or PAY" autoCapitalize="characters" /></Field>}
      <Field label="Project name" error={errors.name?.message}><input {...register("name")} autoFocus placeholder="Payments platform" /></Field>
      <Field label="Client" error={errors.client_name?.message}><input {...register("client_name")} placeholder="Optional client" /></Field>
      <Field label="Status" error={errors.status?.message}><select {...register("status")}>{PROJECT_STATUSES.map((value) => <option key={value}>{value}</option>)}</select></Field>
      <Field label="Priority" error={errors.priority?.message}><select {...register("priority")}>{PRIORITIES.map((value) => <option key={value}>{value}</option>)}</select></Field>
      <Field label="Start date" error={errors.start_date?.message}><input type="date" {...register("start_date")} /></Field>
      <Field label="Expected end" error={errors.expected_end_date?.message}><input type="date" {...register("expected_end_date")} /></Field>
      <div className={styles.span2}><Field label="Description" error={errors.description?.message}><textarea {...register("description")} placeholder="Purpose, outcomes and scope" /></Field></div>
      <div className={styles.span2}><Field label="Remarks" error={errors.remarks?.message}><textarea {...register("remarks")} placeholder="Internal notes" /></Field></div>
      {errors.root?.message && <div className={`${styles.inlineAlert} ${styles.span2}`} role="alert">{errors.root.message}</div>}
      <div className={styles.formActions}>
        <Button type="button" variant="secondary" onClick={() => isDirty ? setConfirmClose(true) : onCancel()}>Cancel{isDirty ? " changes" : ""}</Button>
        <Button type="submit" loading={mutation.isPending} loadingLabel="Saving…">{project ? "Save changes" : "Create project"}</Button>
      </div>
      <ConfirmDialog open={confirmClose} title="Discard unsaved changes?" description="Your project edits have not been saved." confirmLabel="Discard changes" destructive onCancel={() => setConfirmClose(false)} onConfirm={onCancel} />
    </form>
  );
};
