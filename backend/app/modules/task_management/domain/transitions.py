from app.modules.task_management.domain.enums import ProjectStatus, TaskStatus


PROJECT_TRANSITIONS: dict[ProjectStatus, frozenset[ProjectStatus]] = {
    ProjectStatus.NOT_STARTED: frozenset(
        {ProjectStatus.IN_PROGRESS, ProjectStatus.ON_HOLD, ProjectStatus.CANCELLED}
    ),
    ProjectStatus.IN_PROGRESS: frozenset(
        {ProjectStatus.ON_HOLD, ProjectStatus.COMPLETED, ProjectStatus.CANCELLED}
    ),
    ProjectStatus.ON_HOLD: frozenset(
        {ProjectStatus.IN_PROGRESS, ProjectStatus.CANCELLED}
    ),
    ProjectStatus.COMPLETED: frozenset({ProjectStatus.IN_PROGRESS}),
    ProjectStatus.CANCELLED: frozenset({ProjectStatus.NOT_STARTED}),
}


TASK_TRANSITIONS: dict[TaskStatus, frozenset[TaskStatus]] = {
    TaskStatus.NEW: frozenset(
        {TaskStatus.ASSIGNED, TaskStatus.IN_PROGRESS, TaskStatus.CANCELLED}
    ),
    TaskStatus.ASSIGNED: frozenset(
        {
            TaskStatus.IN_PROGRESS,
            TaskStatus.BLOCKED,
            TaskStatus.ON_HOLD,
            TaskStatus.CANCELLED,
        }
    ),
    TaskStatus.IN_PROGRESS: frozenset(
        {
            TaskStatus.BLOCKED,
            TaskStatus.ON_HOLD,
            TaskStatus.UNDER_REVIEW,
            TaskStatus.COMPLETED,
            TaskStatus.CANCELLED,
        }
    ),
    TaskStatus.BLOCKED: frozenset(
        {TaskStatus.IN_PROGRESS, TaskStatus.ON_HOLD, TaskStatus.CANCELLED}
    ),
    TaskStatus.ON_HOLD: frozenset(
        {TaskStatus.ASSIGNED, TaskStatus.IN_PROGRESS, TaskStatus.CANCELLED}
    ),
    TaskStatus.UNDER_REVIEW: frozenset(
        {TaskStatus.IN_PROGRESS, TaskStatus.BLOCKED, TaskStatus.COMPLETED}
    ),
    TaskStatus.COMPLETED: frozenset({TaskStatus.IN_PROGRESS}),
    TaskStatus.CANCELLED: frozenset({TaskStatus.NEW}),
}


def can_transition_project(current: str, target: str) -> bool:
    if current == target:
        return True
    try:
        return ProjectStatus(target) in PROJECT_TRANSITIONS[ProjectStatus(current)]
    except (KeyError, ValueError):
        return False


def can_transition_task(current: str, target: str) -> bool:
    if current == target:
        return True
    try:
        return TaskStatus(target) in TASK_TRANSITIONS[TaskStatus(current)]
    except (KeyError, ValueError):
        return False

