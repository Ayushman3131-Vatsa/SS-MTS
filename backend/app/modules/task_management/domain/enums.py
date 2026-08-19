from enum import StrEnum


class ProjectStatus(StrEnum):
    NOT_STARTED = "Not Started"
    IN_PROGRESS = "In Progress"
    COMPLETED = "Completed"
    ON_HOLD = "On Hold"
    CANCELLED = "Cancelled"


class TaskStatus(StrEnum):
    NEW = "New"
    ASSIGNED = "Assigned"
    IN_PROGRESS = "In Progress"
    BLOCKED = "Blocked"
    ON_HOLD = "On Hold"
    UNDER_REVIEW = "Under Review"
    COMPLETED = "Completed"
    CANCELLED = "Cancelled"


class Priority(StrEnum):
    LOW = "Low"
    MEDIUM = "Medium"
    HIGH = "High"
    CRITICAL = "Critical"


class TaskType(StrEnum):
    EPIC = "EPIC"
    STORY = "STORY"
    TASK = "TASK"
    BUG = "BUG"
    SUBTASK = "SUBTASK"


class ProjectMemberRole(StrEnum):
    MANAGER = "MANAGER"
    MEMBER = "MEMBER"
    VIEWER = "VIEWER"


class TaskLinkType(StrEnum):
    BLOCKS = "BLOCKS"
    RELATES_TO = "RELATES_TO"
    DUPLICATES = "DUPLICATES"


class ActivityEventType(StrEnum):
    CREATED = "CREATED"
    UPDATED = "UPDATED"
    TRANSITIONED = "TRANSITIONED"
    ASSIGNED = "ASSIGNED"
    COMMENTED = "COMMENTED"
    COMMENT_UPDATED = "COMMENT_UPDATED"
    COMMENT_DELETED = "COMMENT_DELETED"
    TIME_LOGGED = "TIME_LOGGED"
    TIME_UPDATED = "TIME_UPDATED"
    TIME_DELETED = "TIME_DELETED"
    ATTACHMENT_ADDED = "ATTACHMENT_ADDED"
    ATTACHMENT_DELETED = "ATTACHMENT_DELETED"
    LINK_ADDED = "LINK_ADDED"
    LINK_REMOVED = "LINK_REMOVED"
    ARCHIVED = "ARCHIVED"
    RESTORED = "RESTORED"

