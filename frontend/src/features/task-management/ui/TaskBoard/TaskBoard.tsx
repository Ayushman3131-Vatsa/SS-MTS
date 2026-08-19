import {
  DndContext,
  KeyboardSensor,
  PointerSensor,
  TouchSensor,
  closestCorners,
  useDraggable,
  useDroppable,
  useSensor,
  useSensors,
  type DragEndEvent,
} from "@dnd-kit/core";
import { useQueries, useQueryClient } from "@tanstack/react-query";
import { GripVertical } from "lucide-react";
import { useState } from "react";

import { ApiError } from "../../../../shared/api/errors";
import { Button } from "../../../../shared/ui/Button/Button";
import { ConfirmDialog } from "../../../../shared/ui/ConfirmDialog/ConfirmDialog";
import { taskManagementApi } from "../../api/task-management-api";
import { TASK_TRANSITIONS, TERMINAL_STATUSES } from "../../model/constants";
import { formatDate } from "../../model/format";
import { taskManagementKeys } from "../../model/query-keys";
import { TASK_STATUSES, type Page, type Task, type TaskFilters, type TaskStatus, type UserSummary } from "../../model/types";
import { useTaskTenantId } from "../../model/use-task-management";
import { PriorityBadge, TypeBadge, UserAvatar } from "../primitives";
import styles from "../task-management.module.css";

const BoardCard = ({ task, user, movable, onOpen, onMove }: { task: Task; user?: UserSummary; movable: boolean; onOpen: () => void; onMove: (status: TaskStatus) => void }) => {
  const draggable = useDraggable({ id: task.task_id, data: { task }, disabled: !movable });
  return <article ref={draggable.setNodeRef} className={`${styles.boardCard} ${draggable.isDragging ? styles.dragging : ""}`} style={{ transform: draggable.transform ? `translate3d(${draggable.transform.x}px, ${draggable.transform.y}px, 0)` : undefined }}>
    <header><button type="button" className={styles.dragHandle} aria-label={`Move ${task.display_key}`} disabled={!movable} {...draggable.listeners} {...draggable.attributes}><GripVertical size={14} /></button><button type="button" className={styles.linkButton} onClick={onOpen}>{task.display_key}</button><TypeBadge value={task.task_type} /></header>
    <button type="button" className={styles.cardTitle} onClick={onOpen}>{task.name}</button>
    <footer><PriorityBadge value={task.priority} /><span>{formatDate(task.end_date)}</span><UserAvatar user={user} /></footer>
    {movable && <label className={styles.moveMenu}><span className={styles.srOnly}>Move {task.display_key} to</span><select value="" onChange={(event) => { if (event.target.value) onMove(event.target.value as TaskStatus); }}><option value="">Move to…</option>{TASK_TRANSITIONS[task.status].map((status) => <option key={status}>{status}</option>)}</select></label>}
  </article>;
};

const BoardColumn = ({ status, tasks, total, users, canMove, onOpen, onMove, onLoadMore }: { status: TaskStatus; tasks: Task[]; total: number; users: Map<string, UserSummary>; canMove: (task: Task) => boolean; onOpen: (task: Task) => void; onMove: (task: Task, status: TaskStatus) => void; onLoadMore: () => void }) => {
  const drop = useDroppable({ id: status });
  return <section ref={drop.setNodeRef} className={`${styles.boardColumn} ${drop.isOver ? styles.columnOver : ""}`} aria-label={`${status} tasks`}>
    <header><strong>{status}</strong><span>{total}</span></header>
    <div>{tasks.map((task) => <BoardCard key={task.task_id} task={task} user={task.assignee_id ? users.get(task.assignee_id) : undefined} movable={canMove(task)} onOpen={() => onOpen(task)} onMove={(target) => onMove(task, target)} />)}{!tasks.length && <p>Drop eligible tasks here</p>}</div>
    {tasks.length < total && <Button type="button" variant="ghost" className={styles.loadMore} onClick={onLoadMore}>Load more</Button>}
  </section>;
};

export const TaskBoard = ({ projectId, filters, users, canMove, onOpen }: { projectId: string; filters: TaskFilters; users: UserSummary[]; canMove: (task: Task) => boolean; onOpen: (task: Task) => void }) => {
  const tenantId = useTaskTenantId();
  const client = useQueryClient();
  const [limits, setLimits] = useState<Record<TaskStatus, number>>(() => Object.fromEntries(TASK_STATUSES.map((status) => [status, 20])) as Record<TaskStatus, number>);
  const [pending, setPending] = useState<{ task: Task; target: TaskStatus } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [moving, setMoving] = useState(false);
  const sensors = useSensors(useSensor(PointerSensor, { activationConstraint: { distance: 6 } }), useSensor(TouchSensor, { activationConstraint: { delay: 180, tolerance: 7 } }), useSensor(KeyboardSensor));
  const boardFilters = TASK_STATUSES.map((status) => ({ ...filters, project_id: projectId, status, page: 1, page_size: limits[status], sort: "task_number" }));
  const results = useQueries({ queries: boardFilters.map((queryFilters) => ({ queryKey: taskManagementKeys.tasks(tenantId, queryFilters), queryFn: ({ signal }: { signal: AbortSignal }) => taskManagementApi.tasks(queryFilters, signal), placeholderData: (previous: Page<Task> | undefined) => previous })) });
  const allTasks = results.flatMap((result) => result.data?.items ?? []);
  const usersById = new Map(users.map((user) => [user.user_id, user]));
  const executeMove = async (task: Task, target: TaskStatus) => {
    setMoving(true); setError(null);
    const snapshots = boardFilters.map((queryFilters) => [taskManagementKeys.tasks(tenantId, queryFilters), client.getQueryData(taskManagementKeys.tasks(tenantId, queryFilters))] as const);
    boardFilters.forEach((queryFilters) => client.setQueryData<Page<Task>>(taskManagementKeys.tasks(tenantId, queryFilters), (old) => {
      if (!old) return old;
      if (queryFilters.status === task.status) return { ...old, items: old.items.filter((item) => item.task_id !== task.task_id), total: Math.max(0, old.total - 1) };
      if (queryFilters.status === target) return { ...old, items: [{ ...task, status: target }, ...old.items], total: old.total + 1 };
      return old;
    }));
    try { await taskManagementApi.transitionTask(task.task_id, target, task.version); await client.invalidateQueries({ queryKey: taskManagementKeys.root(tenantId) }); }
    catch (cause) { snapshots.forEach(([key, value]) => client.setQueryData(key, value)); setError(cause instanceof ApiError && cause.status === 409 ? "This board was out of date. The move was rolled back; reload before trying again." : cause instanceof Error ? `${cause.message} The move was rolled back.` : "The move failed and was rolled back."); throw cause; }
    finally { setMoving(false); }
  };
  const move = (task: Task, target: TaskStatus) => {
    if (!TASK_TRANSITIONS[task.status].includes(target)) return;
    if (TERMINAL_STATUSES.includes(target)) { setPending({ task, target }); return; }
    void executeMove(task, target).catch(() => undefined);
  };
  const endDrag = (event: DragEndEvent) => {
    const task = allTasks.find((item) => item.task_id === event.active.id);
    const target = event.over?.id as TaskStatus | undefined;
    if (task && target && task.status !== target && TASK_STATUSES.includes(target) && canMove(task)) move(task, target);
  };
  return <>
    {error && <div className={styles.inlineAlert} role="alert">{error} <button type="button" onClick={() => void client.invalidateQueries({ queryKey: taskManagementKeys.root(tenantId) })}>Reload board</button></div>}
    <DndContext sensors={sensors} collisionDetection={closestCorners} onDragEnd={endDrag}>
      <div className={styles.board} aria-busy={moving}>{TASK_STATUSES.map((status, index) => <BoardColumn key={status} status={status} tasks={results[index].data?.items ?? []} total={results[index].data?.total ?? 0} users={usersById} canMove={canMove} onOpen={onOpen} onMove={move} onLoadMore={() => setLimits((current) => ({ ...current, [status]: Math.min(100, current[status] + 20) }))} />)}</div>
    </DndContext>
    <ConfirmDialog open={Boolean(pending)} title={`Move to ${pending?.target ?? "terminal state"}?`} description={pending?.target === "Completed" ? "The task can complete only when every child is completed or cancelled." : "Cancellation is recorded in task activity and can be reopened later."} confirmLabel={`Move to ${pending?.target ?? "status"}`} busy={moving} onCancel={() => setPending(null)} onConfirm={() => { if (!pending) return; void executeMove(pending.task, pending.target).then(() => setPending(null)).catch(() => undefined); }} />
  </>;
};

