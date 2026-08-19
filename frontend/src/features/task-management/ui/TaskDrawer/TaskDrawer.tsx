import { useQuery } from "@tanstack/react-query";
import { Download, Edit3, FilePlus2, Link2, MessageSquare, Paperclip, Plus, Timer, Trash2 } from "lucide-react";
import { type FormEvent, useEffect, useState } from "react";

import { useSession } from "../../../../entities/session/model/session-context";
import { ApiError } from "../../../../shared/api/errors";
import { Button } from "../../../../shared/ui/Button/Button";
import { ConfirmDialog } from "../../../../shared/ui/ConfirmDialog/ConfirmDialog";
import { taskManagementApi } from "../../api/task-management-api";
import { ATTACHMENT_ACCEPT, MAX_ATTACHMENT_BYTES, TASK_TRANSITIONS, TERMINAL_STATUSES } from "../../model/constants";
import { activityLabel, formatBytes, formatDate, formatHours } from "../../model/format";
import { canCollaborate, canExecuteTask, canManageProject } from "../../model/permissions";
import { taskManagementKeys } from "../../model/query-keys";
import { LINK_TYPES, PRIORITIES, type Project, type Task, type TaskComment, type TimeEntry, type UserSummary } from "../../model/types";
import { useMembers, useTask, useTaskMutation, useTaskTenantId, useTasks } from "../../model/use-task-management";
import { ErrorState, Field, LoadingState, Overlay, PriorityBadge, StatusBadge, TypeBadge, UserAvatar } from "../primitives";
import styles from "../task-management.module.css";

type DetailTab = "fields" | "comments" | "time" | "files" | "links" | "activity";
interface Confirmation { title: string; description: string; label: string; destructive?: boolean; run: () => Promise<unknown>; }

const TaskFields = ({ task, users, editable }: { task: Task; users: UserSummary[]; editable: boolean }) => {
  const [editing, setEditing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const mutation = useTaskMutation((input: Parameters<typeof taskManagementApi.updateTask>[1]) => taskManagementApi.updateTask(task.task_id, input));
  const userById = new Map(users.map((user) => [user.user_id, user]));
  const activeUsers = users.filter((user) => user.status === "Active");
  if (!editing) return <div className={styles.detailSection}>
    {editable && !task.archived_at && <div className={styles.sectionActions}><Button type="button" variant="secondary" className={styles.compactButton} onClick={() => setEditing(true)}><Edit3 size={14} /> Edit fields</Button></div>}
    <dl className={styles.detailGrid}>
      <div><dt>Type</dt><dd><TypeBadge value={task.task_type} /></dd></div><div><dt>Priority</dt><dd><PriorityBadge value={task.priority} /></dd></div>
      <div><dt>Assignee</dt><dd><UserAvatar user={task.assignee_id ? userById.get(task.assignee_id) : undefined} /> {task.assignee_id ? userById.get(task.assignee_id)?.name ?? "Inactive/unknown user" : "Unassigned"}</dd></div>
      <div><dt>Reporter</dt><dd>{task.reporter_id ? userById.get(task.reporter_id)?.name ?? "Unknown user" : "—"}</dd></div>
      <div><dt>Technical lead</dt><dd>{task.technical_lead_id ? userById.get(task.technical_lead_id)?.name ?? "Unknown user" : "—"}</dd></div><div><dt>Functional lead</dt><dd>{task.functional_lead_id ? userById.get(task.functional_lead_id)?.name ?? "Unknown user" : "—"}</dd></div>
      <div><dt>Start date</dt><dd>{formatDate(task.start_date)}</dd></div><div><dt>Due date</dt><dd>{formatDate(task.end_date)}</dd></div>
      <div><dt>Estimate</dt><dd>{formatHours(task.estimated_hours)}</dd></div><div><dt>Actual</dt><dd>{formatHours(task.actual_hours)}</dd></div>
      <div><dt>Category</dt><dd>{task.task_category ?? "—"}</dd></div><div><dt>Version</dt><dd>{task.version}</dd></div>
      <div className={styles.detailWide}><dt>Description</dt><dd>{task.description || "No description provided."}</dd></div><div className={styles.detailWide}><dt>Remarks</dt><dd>{task.remarks || "No remarks."}</dd></div>
    </dl>
  </div>;
  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault(); setError(null);
    const data = new FormData(event.currentTarget);
    try {
      await mutation.mutateAsync({
        name: String(data.get("name") ?? "").trim(), priority: String(data.get("priority")) as Task["priority"],
        assignee_id: String(data.get("assignee_id") || "") || null,
        technical_lead_id: String(data.get("technical_lead_id") || "") || null,
        functional_lead_id: String(data.get("functional_lead_id") || "") || null,
        task_category: String(data.get("task_category") || "") || null,
        start_date: String(data.get("start_date") || "") || null, end_date: String(data.get("end_date") || "") || null,
        estimated_hours: Number(data.get("estimated_hours") ?? 0), description: String(data.get("description") || "") || null,
        remarks: String(data.get("remarks") || "") || null, version: task.version,
      });
      setEditing(false);
    } catch (cause) { setError(cause instanceof ApiError && cause.status === 409 ? "This task is out of date. Your draft is preserved; reload before trying again." : cause instanceof Error ? cause.message : "Could not save task fields."); }
  };
  return <form className={styles.formGrid} onSubmit={submit}>
    <div className={styles.span2}><Field label="Summary"><input name="name" defaultValue={task.name} required /></Field></div>
    <Field label="Priority"><select name="priority" defaultValue={task.priority}>{PRIORITIES.map((value) => <option key={value}>{value}</option>)}</select></Field>
    <Field label="Assignee"><select name="assignee_id" defaultValue={task.assignee_id ?? ""}><option value="">Unassigned</option>{activeUsers.map((user) => <option key={user.user_id} value={user.user_id}>{user.name}</option>)}</select></Field>
    <Field label="Technical lead"><select name="technical_lead_id" defaultValue={task.technical_lead_id ?? ""}><option value="">None</option>{activeUsers.map((user) => <option key={user.user_id} value={user.user_id}>{user.name}</option>)}</select></Field>
    <Field label="Functional lead"><select name="functional_lead_id" defaultValue={task.functional_lead_id ?? ""}><option value="">None</option>{activeUsers.map((user) => <option key={user.user_id} value={user.user_id}>{user.name}</option>)}</select></Field>
    <Field label="Category"><input name="task_category" defaultValue={task.task_category ?? ""} /></Field><Field label="Estimate"><input name="estimated_hours" type="number" step=".25" min="0" defaultValue={task.estimated_hours} /></Field>
    <Field label="Start date"><input name="start_date" type="date" defaultValue={task.start_date ?? ""} /></Field><Field label="Due date"><input name="end_date" type="date" defaultValue={task.end_date ?? ""} /></Field>
    <div className={styles.span2}><Field label="Description"><textarea name="description" defaultValue={task.description ?? ""} /></Field></div><div className={styles.span2}><Field label="Remarks"><textarea name="remarks" defaultValue={task.remarks ?? ""} /></Field></div>
    {error && <div className={`${styles.inlineAlert} ${styles.span2}`} role="alert">{error}</div>}
    <div className={styles.formActions}><Button type="button" variant="secondary" onClick={() => setEditing(false)}>Cancel</Button><Button type="submit" loading={mutation.isPending}>Save changes</Button></div>
  </form>;
};

export const TaskDrawer = ({ taskId, projects, users, onClose }: { taskId?: string; projects: Project[]; users: UserSummary[]; onClose: () => void }) => {
  const { principal } = useSession();
  const tenantId = useTaskTenantId();
  const taskQuery = useTask(taskId);
  const task = taskQuery.data;
  const membersQuery = useMembers(task?.project_id);
  const candidateTasks = useTasks({ project_id: task?.project_id, page_size: 100, sort: "task_number" });
  const [tab, setTab] = useState<DetailTab>("fields");
  const [confirmation, setConfirmation] = useState<Confirmation | null>(null);
  const [confirmBusy, setConfirmBusy] = useState(false);
  const [transitionError, setTransitionError] = useState<string | null>(null);
  const tenantPrincipal = principal?.principal_type === "tenant_user" ? principal : null;
  const member = membersQuery.data?.items.find((item) => item.user_id === tenantPrincipal?.principal_id);
  const access = { tenantRole: tenantPrincipal?.role ?? "Employee", memberRole: member?.role, principalId: tenantPrincipal?.principal_id ?? "" };
  const mayManage = canManageProject(access);
  const mayExecute = task ? canExecuteTask(access, task) : false;
  const mayCollaborate = canCollaborate(access);
  const transition = useTaskMutation(({ target, reason }: { target: Task["status"]; reason?: string }) => taskManagementApi.transitionTask(task!.task_id, target, task!.version, reason));

  useEffect(() => { if (!taskId) setTab("fields"); }, [taskId]);
  const move = (target: Task["status"]) => {
    const run = async () => { setTransitionError(null); try { await transition.mutateAsync({ target }); } catch (error) { setTransitionError(error instanceof ApiError && error.status === 409 ? "This task is out of date. Reload it before moving." : error instanceof Error ? error.message : "Could not move the task."); throw error; } };
    if (TERMINAL_STATUSES.includes(target)) setConfirmation({ title: `Move to ${target}?`, description: target === "Completed" ? "All child tasks must already be completed or cancelled." : "Cancelled work remains in activity history and can be reopened.", label: `Move to ${target}`, run });
    else void run();
  };
  const confirmAction = async () => { if (!confirmation) return; setConfirmBusy(true); try { await confirmation.run(); setConfirmation(null); } catch { /* The owning panel renders the error. */ } finally { setConfirmBusy(false); } };
  const project = projects.find((item) => item.project_id === task?.project_id);
  return <>
    <Overlay open={Boolean(taskId)} title={task ? `${task.display_key} · ${task.name}` : "Task details"} description={project ? `${project.project_key} · ${project.name}` : undefined} mode="drawer" wide onClose={onClose}>
      {taskQuery.isPending ? <LoadingState rows={8} /> : taskQuery.isError ? <ErrorState message={taskQuery.error.message} onRetry={() => void taskQuery.refetch()} /> : task ? <div className={styles.taskDetail}>
        <div className={styles.taskMeta}><TypeBadge value={task.task_type} /><StatusBadge value={task.status} /><PriorityBadge value={task.priority} />{task.archived_at && <span className={styles.readOnlyFlag}>Archived · read only</span>}</div>
        {(mayExecute || mayManage) && !task.archived_at && <div className={styles.transitionBar}><strong>Move to</strong>{TASK_TRANSITIONS[task.status].map((target) => <Button key={target} type="button" variant="secondary" className={styles.compactButton} disabled={transition.isPending} onClick={() => move(target)}>{target}</Button>)}</div>}
        {transitionError && <div className={styles.inlineAlert} role="alert">{transitionError} <button type="button" onClick={() => void taskQuery.refetch()}>Reload task</button></div>}
        <nav className={styles.detailTabs} aria-label="Task details">{([['fields','Fields',Edit3],['comments','Comments',MessageSquare],['time','Time',Timer],['files','Files',Paperclip],['links','Links',Link2],['activity','Activity',CircleIcon]] as const).map(([value, label, Icon]) => <button key={value} type="button" className={tab === value ? styles.tabActive : ""} aria-current={tab === value ? "page" : undefined} onClick={() => setTab(value)}><Icon size={14} />{label}</button>)}</nav>
        {tab === "fields" && <TaskFields task={task} users={users} editable={mayManage} />}
        {tab === "comments" && <CommentsPanel task={task} users={users} mayCollaborate={mayCollaborate && !task.archived_at} mayModerate={mayManage} onConfirm={setConfirmation} tenantId={tenantId} principalId={tenantPrincipal?.principal_id ?? ""} />}
        {tab === "time" && <TimePanel task={task} users={users} mayLog={(mayExecute || mayManage) && !task.archived_at} mayModerate={mayManage} onConfirm={setConfirmation} tenantId={tenantId} principalId={tenantPrincipal?.principal_id ?? ""} />}
        {tab === "files" && <FilesPanel task={task} users={users} mayCollaborate={mayCollaborate && !task.archived_at} mayModerate={mayManage} principalId={tenantPrincipal?.principal_id ?? ""} onConfirm={setConfirmation} tenantId={tenantId} />}
        {tab === "links" && <LinksPanel task={task} tasks={candidateTasks.data?.items ?? []} mayManage={mayManage && !task.archived_at} onConfirm={setConfirmation} tenantId={tenantId} />}
        {tab === "activity" && <ActivityPanel task={task} users={users} tenantId={tenantId} />}
      </div> : null}
    </Overlay>
    <ConfirmDialog open={Boolean(confirmation)} title={confirmation?.title ?? "Confirm action"} description={confirmation?.description ?? ""} confirmLabel={confirmation?.label ?? "Confirm"} destructive={confirmation?.destructive} busy={confirmBusy} onCancel={() => setConfirmation(null)} onConfirm={() => void confirmAction()} />
  </>;
};

const CircleIcon = ({ size }: { size?: number }) => <span className={styles.circleIcon} style={{ width: size, height: size }} />;

const CommentsPanel = ({ task, users, mayCollaborate, mayModerate, onConfirm, tenantId, principalId }: { task: Task; users: UserSummary[]; mayCollaborate: boolean; mayModerate: boolean; onConfirm: (value: Confirmation) => void; tenantId: string; principalId: string }) => {
  const query = useQuery({ queryKey: taskManagementKeys.comments(tenantId, task.task_id), queryFn: ({ signal }) => taskManagementApi.comments(task.task_id, signal) });
  const [text, setText] = useState(""); const [editing, setEditing] = useState<TaskComment | null>(null); const [error, setError] = useState<string | null>(null);
  const save = useTaskMutation(() => editing ? taskManagementApi.updateComment(task.task_id, editing.comment_id, text.trim(), editing.version) : taskManagementApi.createComment(task.task_id, text.trim()));
  const remove = useTaskMutation((comment: TaskComment) => taskManagementApi.deleteComment(task.task_id, comment.comment_id, comment.version));
  const userById = new Map(users.map((user) => [user.user_id, user]));
  const submit = async (event: FormEvent) => { event.preventDefault(); if (!text.trim()) return; setError(null); try { await save.mutateAsync(); setText(""); setEditing(null); } catch (cause) { setError(cause instanceof Error ? cause.message : "Could not save comment."); } };
  return <section className={styles.collaborationPanel}>{mayCollaborate && <form className={styles.composer} onSubmit={submit}><textarea value={text} onChange={(event) => setText(event.target.value)} placeholder="Add context or an update…" aria-label="Comment" maxLength={20_000} /><div>{editing && <Button type="button" variant="ghost" onClick={() => { setEditing(null); setText(""); }}>Cancel edit</Button>}<Button type="submit" disabled={!text.trim()} loading={save.isPending}>{editing ? "Save comment" : "Comment"}</Button></div>{error && <small role="alert">{error}</small>}</form>}
    {query.isPending ? <LoadingState /> : query.isError ? <ErrorState message={query.error.message} onRetry={() => void query.refetch()} /> : <div className={styles.feed}>{query.data.items.length === 0 && <p className={styles.muted}>No comments yet.</p>}{query.data.items.map((comment) => { const own = comment.commented_by_user_id === principalId; return <article key={comment.comment_id}><UserAvatar user={userById.get(comment.commented_by_user_id)} /><div><header><strong>{userById.get(comment.commented_by_user_id)?.name ?? "Unknown user"}</strong><time>{formatDate(comment.updated_at, true)}</time>{(own || mayModerate) && <span><button type="button" onClick={() => { setEditing(comment); setText(comment.comment_text); }} aria-label="Edit comment"><Edit3 size={13} /></button><button type="button" onClick={() => onConfirm({ title: "Delete this comment?", description: "The comment is removed from the conversation but remains represented in activity history.", label: "Delete comment", destructive: true, run: () => remove.mutateAsync(comment) })} aria-label="Delete comment"><Trash2 size={13} /></button></span>}</header><p>{comment.comment_text}</p></div></article>; })}</div>}
  </section>;
};

const TimePanel = ({ task, users, mayLog, mayModerate, onConfirm, tenantId, principalId }: { task: Task; users: UserSummary[]; mayLog: boolean; mayModerate: boolean; onConfirm: (value: Confirmation) => void; tenantId: string; principalId: string }) => {
  const query = useQuery({ queryKey: taskManagementKeys.time(tenantId, task.task_id), queryFn: ({ signal }) => taskManagementApi.timeEntries(task.task_id, signal) });
  const [editing, setEditing] = useState<TimeEntry | null>(null); const [hours, setHours] = useState(""); const [workDate, setWorkDate] = useState(new Date().toISOString().slice(0, 10)); const [notes, setNotes] = useState("");
  const save = useTaskMutation(() => editing ? taskManagementApi.updateTimeEntry(task.task_id, editing.log_id, { hours_worked: Number(hours), work_date: workDate, progress_notes: notes || null, version: editing.version }) : taskManagementApi.createTimeEntry(task.task_id, { hours_worked: Number(hours), work_date: workDate, progress_notes: notes || null }));
  const remove = useTaskMutation((entry: TimeEntry) => taskManagementApi.deleteTimeEntry(task.task_id, entry.log_id, entry.version));
  const usersById = new Map(users.map((user) => [user.user_id, user]));
  const reset = () => { setEditing(null); setHours(""); setNotes(""); setWorkDate(new Date().toISOString().slice(0, 10)); };
  return <section className={styles.collaborationPanel}>{mayLog && <form className={styles.inlineForm} onSubmit={(event) => { event.preventDefault(); void save.mutateAsync().then(reset); }}><Field label="Work date"><input type="date" value={workDate} onChange={(event) => setWorkDate(event.target.value)} required /></Field><Field label="Hours"><input type="number" min=".01" max="24" step=".25" value={hours} onChange={(event) => setHours(event.target.value)} required /></Field><Field label="Notes"><input value={notes} onChange={(event) => setNotes(event.target.value)} placeholder="What changed?" /></Field><div>{editing && <Button type="button" variant="ghost" onClick={reset}>Cancel</Button>}<Button type="submit" loading={save.isPending}>{editing ? "Save" : "Log time"}</Button></div></form>}
    {query.isPending ? <LoadingState /> : query.isError ? <ErrorState message={query.error.message} onRetry={() => void query.refetch()} /> : <div className={styles.feed}>{query.data.items.length === 0 && <p className={styles.muted}>No time logged yet.</p>}{query.data.items.map((entry) => { const own = entry.updated_by_user_id === principalId; return <article key={entry.log_id}><UserAvatar user={usersById.get(entry.updated_by_user_id)} /><div><header><strong>{formatHours(entry.hours_worked)} · {usersById.get(entry.updated_by_user_id)?.name ?? "Unknown user"}</strong><time>{formatDate(entry.work_date)}</time>{(own || mayModerate) && <span><button type="button" aria-label="Edit time entry" onClick={() => { setEditing(entry); setHours(String(entry.hours_worked)); setWorkDate(entry.work_date); setNotes(entry.progress_notes ?? ""); }}><Edit3 size={13} /></button><button type="button" aria-label="Delete time entry" onClick={() => onConfirm({ title: "Delete this time entry?", description: `${formatHours(entry.hours_worked)} will be removed from actual hours.`, label: "Delete time entry", destructive: true, run: () => remove.mutateAsync(entry) })}><Trash2 size={13} /></button></span>}</header><p>{entry.progress_notes || "No notes."}</p></div></article>; })}</div>}
  </section>;
};

const FilesPanel = ({ task, users, mayCollaborate, mayModerate, principalId, onConfirm, tenantId }: { task: Task; users: UserSummary[]; mayCollaborate: boolean; mayModerate: boolean; principalId: string; onConfirm: (value: Confirmation) => void; tenantId: string }) => {
  const query = useQuery({ queryKey: taskManagementKeys.attachments(tenantId, task.task_id), queryFn: ({ signal }) => taskManagementApi.attachments(task.task_id, signal) });
  const [error, setError] = useState<string | null>(null);
  const upload = useTaskMutation((file: File) => taskManagementApi.uploadAttachment(task.task_id, file)); const remove = useTaskMutation((id: string) => taskManagementApi.deleteAttachment(task.task_id, id));
  const userById = new Map(users.map((user) => [user.user_id, user]));
  const choose = (file?: File) => { if (!file) return; setError(null); if (file.size > MAX_ATTACHMENT_BYTES) { setError("This file exceeds the 10 MiB limit."); return; } if (!ATTACHMENT_ACCEPT.split(",").includes(file.type)) { setError("This file type is not allowed."); return; } void upload.mutateAsync(file).catch((cause) => setError(cause instanceof Error ? cause.message : "Upload failed.")); };
  return <section className={styles.collaborationPanel}>{mayCollaborate && <label className={styles.dropzone}><FilePlus2 size={20} /><strong>{upload.isPending ? "Uploading…" : "Choose a file to attach"}</strong><span>PDF, images, text and office documents · maximum 10 MiB</span><input type="file" accept={ATTACHMENT_ACCEPT} disabled={upload.isPending} onChange={(event) => choose(event.target.files?.[0])} /></label>}{error && <div className={styles.inlineAlert} role="alert">{error}</div>}
    {query.isPending ? <LoadingState /> : query.isError ? <ErrorState message={query.error.message} onRetry={() => void query.refetch()} /> : <div className={styles.fileList}>{query.data.items.length === 0 && <p className={styles.muted}>No files attached.</p>}{query.data.items.map((file) => <article key={file.attachment_id}><Paperclip size={16} /><div><strong>{file.original_filename}</strong><span>{formatBytes(file.size_bytes)} · {userById.get(file.uploaded_by_user_id)?.name ?? "Unknown user"} · {formatDate(file.created_at, true)}</span></div><button type="button" aria-label={`Download ${file.original_filename}`} onClick={() => void taskManagementApi.downloadAttachment(task.task_id, file.attachment_id).then(({ blob, filename }) => { const url = URL.createObjectURL(blob); const anchor = document.createElement("a"); anchor.href = url; anchor.download = filename ?? file.original_filename; anchor.click(); URL.revokeObjectURL(url); })}><Download size={15} /></button>{mayCollaborate && (mayModerate || file.uploaded_by_user_id === principalId) && <button type="button" aria-label={`Delete ${file.original_filename}`} onClick={() => onConfirm({ title: "Delete this attachment?", description: `${file.original_filename} will no longer be downloadable.`, label: "Delete attachment", destructive: true, run: () => remove.mutateAsync(file.attachment_id) })}><Trash2 size={15} /></button>}</article>)}</div>}
  </section>;
};

const LinksPanel = ({ task, tasks, mayManage, onConfirm, tenantId }: { task: Task; tasks: Task[]; mayManage: boolean; onConfirm: (value: Confirmation) => void; tenantId: string }) => {
  const query = useQuery({ queryKey: taskManagementKeys.links(tenantId, task.task_id), queryFn: ({ signal }) => taskManagementApi.links(task.task_id, signal) });
  const [target, setTarget] = useState(""); const [type, setType] = useState<(typeof LINK_TYPES)[number]>("RELATES_TO");
  const create = useTaskMutation(() => taskManagementApi.createLink(task.task_id, target, type)); const remove = useTaskMutation((id: string) => taskManagementApi.deleteLink(task.task_id, id));
  const taskById = new Map(tasks.map((item) => [item.task_id, item]));
  return <section className={styles.collaborationPanel}>{mayManage && <form className={styles.inlineForm} onSubmit={(event) => { event.preventDefault(); void create.mutateAsync().then(() => setTarget("")); }}><Field label="Link type"><select value={type} onChange={(event) => setType(event.target.value as typeof type)}>{LINK_TYPES.map((item) => <option key={item} value={item}>{item.replaceAll("_", " ")}</option>)}</select></Field><Field label="Task"><select value={target} onChange={(event) => setTarget(event.target.value)} required><option value="">Select task</option>{tasks.filter((item) => item.task_id !== task.task_id).map((item) => <option key={item.task_id} value={item.task_id}>{item.display_key} · {item.name}</option>)}</select></Field><Button type="submit" disabled={!target} loading={create.isPending}><Plus size={14} /> Add link</Button></form>}
    {query.isPending ? <LoadingState /> : query.isError ? <ErrorState message={query.error.message} onRetry={() => void query.refetch()} /> : <div className={styles.fileList}>{query.data.items.length === 0 && <p className={styles.muted}>No linked tasks.</p>}{query.data.items.map((link) => { const otherId = link.source_task_id === task.task_id ? link.target_task_id : link.source_task_id; const other = taskById.get(otherId); return <article key={link.link_id}><Link2 size={16} /><div><strong>{link.link_type.replaceAll("_", " ")}</strong><span>{other ? `${other.display_key} · ${other.name}` : otherId}</span></div>{mayManage && <button type="button" aria-label="Delete task link" onClick={() => onConfirm({ title: "Delete this task link?", description: "This dependency relationship will be removed.", label: "Delete link", destructive: true, run: () => remove.mutateAsync(link.link_id) })}><Trash2 size={15} /></button>}</article>; })}</div>}
  </section>;
};

const ActivityPanel = ({ task, users, tenantId }: { task: Task; users: UserSummary[]; tenantId: string }) => {
  const query = useQuery({ queryKey: taskManagementKeys.activity(tenantId, task.task_id), queryFn: ({ signal }) => taskManagementApi.activity(task.task_id, signal) });
  const userById = new Map(users.map((user) => [user.user_id, user]));
  return <section className={styles.collaborationPanel}>{query.isPending ? <LoadingState /> : query.isError ? <ErrorState message={query.error.message} onRetry={() => void query.refetch()} /> : <ol className={styles.activity}>{query.data.items.length === 0 && <p className={styles.muted}>No activity recorded.</p>}{query.data.items.map((event) => <li key={event.event_id}><span /><div><strong>{event.actor_user_id ? userById.get(event.actor_user_id)?.name ?? "Unknown user" : "System"}</strong> {activityLabel(event.event_type)}<time>{formatDate(event.occurred_at, true)}</time></div></li>)}</ol>}</section>;
};
