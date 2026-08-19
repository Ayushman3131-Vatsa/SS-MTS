import asyncio
import io
import tempfile
import unittest
from datetime import date
from pathlib import Path

from pydantic import ValidationError
from starlette.datastructures import Headers, UploadFile

from app.core.config import Settings
from app.core.exceptions import BusinessRuleError
from app.db.session import DatabaseSessionManager
from app.main import app
from app.models.project import Project as LegacyProject
from app.models.task import Task as LegacyTask
from app.modules.task_management.attachments.local_storage import LocalAttachmentStorage
from app.modules.task_management.attachments.service import _safe_filename
from app.modules.task_management.domain.enums import ProjectMemberRole, TaskStatus
from app.modules.task_management.domain.policies import (
    ProjectAccess,
    can_comment_or_attach,
    can_create_task,
    can_execute_task,
    can_manage_project,
    can_view_project,
)
from app.modules.task_management.domain.transitions import can_transition_task
from app.modules.task_management.projects.model import Project
from app.modules.task_management.projects.schemas import ProjectCreateRequest
from app.modules.task_management.tasks.model import Task
from app.modules.task_management.tasks.schemas import TaskCreateRequest


class TaskManagementDomainTests(unittest.TestCase):
    def test_authoritative_models_keep_legacy_import_identity(self) -> None:
        self.assertIs(Project, LegacyProject)
        self.assertIs(Task, LegacyTask)
        self.assertEqual(Project.__tablename__, "projects")
        self.assertEqual(Task.__tablename__, "tasks")

    def test_fixed_workflow_accepts_only_documented_transitions(self) -> None:
        self.assertTrue(can_transition_task(TaskStatus.NEW, TaskStatus.ASSIGNED))
        self.assertTrue(can_transition_task(TaskStatus.IN_PROGRESS, TaskStatus.UNDER_REVIEW))
        self.assertTrue(can_transition_task(TaskStatus.COMPLETED, TaskStatus.IN_PROGRESS))
        self.assertFalse(can_transition_task(TaskStatus.NEW, TaskStatus.COMPLETED))
        self.assertFalse(can_transition_task(TaskStatus.CANCELLED, TaskStatus.COMPLETED))
        self.assertFalse(can_transition_task("unknown", TaskStatus.NEW))

    def test_project_collaboration_policy_matrix(self) -> None:
        tenant_admin = ProjectAccess("Tenant Admin", None)
        manager = ProjectAccess("Project Manager", ProjectMemberRole.MANAGER)
        member = ProjectAccess("Employee", ProjectMemberRole.MEMBER)
        viewer = ProjectAccess("Employee", ProjectMemberRole.VIEWER)
        assignee = ProjectAccess("Employee", ProjectMemberRole.MEMBER, is_assignee=True)

        self.assertTrue(can_manage_project(tenant_admin))
        self.assertTrue(can_manage_project(manager))
        self.assertTrue(can_create_task(member))
        self.assertTrue(can_comment_or_attach(member))
        self.assertTrue(can_view_project(viewer))
        self.assertFalse(can_create_task(viewer))
        self.assertTrue(can_execute_task(assignee))
        self.assertFalse(can_execute_task(member))

    def test_canonical_schemas_reject_invalid_estimate_and_date_order(self) -> None:
        with self.assertRaises(ValidationError):
            TaskCreateRequest(name="Invalid", estimated_hours="-1")
        with self.assertRaises(ValidationError):
            TaskCreateRequest(
                name="Invalid dates",
                estimated_hours="1",
                start_date=date(2026, 8, 12),
                end_date=date(2026, 8, 11),
            )
        with self.assertRaises(ValidationError):
            ProjectCreateRequest(
                project_key="bad-key",
                name="Invalid key",
            )

    def test_openapi_keeps_legacy_and_canonical_routes(self) -> None:
        paths = app.openapi()["paths"]
        self.assertIn("/projects", paths)
        self.assertIn("/tasks", paths)
        self.assertIn("/tasks/{task_id}/comments", paths)
        self.assertIn("/tasks/{task_id}/logs", paths)
        self.assertIn("/task-management/projects", paths)
        self.assertIn("/task-management/tasks", paths)
        self.assertIn("/task-management/tasks/{task_id}/transitions", paths)
        for path in (
            "/task-management/projects",
            "/task-management/projects/{project_id}/members",
            "/task-management/tasks",
            "/task-management/tasks/{task_id}/links",
            "/task-management/tasks/{task_id}/comments",
            "/task-management/tasks/{task_id}/time-entries",
            "/task-management/tasks/{task_id}/attachments",
            "/task-management/tasks/{task_id}/activity",
        ):
            response_schema = paths[path]["get"]["responses"]["200"]["content"][
                "application/json"
            ]["schema"]
            self.assertIn("PageResponse", response_schema["$ref"])

    def test_production_requires_separate_database_roles(self) -> None:
        common = {
            "_env_file": None,
            "environment": "production",
            "jwt_secret_key": "x" * 32,
            "database_url": "postgresql+asyncpg://app:secret@db/app",
        }
        with self.assertRaises(ValidationError):
            Settings(**common)
        with self.assertRaises(ValidationError):
            Settings(
                **common,
                migration_database_url=common["database_url"],
            )
        with self.assertRaises(ValidationError):
            Settings(
                **common,
                migration_database_url="postgresql+asyncpg://app:other@db/app",
            )
        valid = Settings(
            **common,
            migration_database_url="postgresql+asyncpg://owner:secret@db/app",
        )
        self.assertFalse(valid.is_development)


class LocalAttachmentStorageTests(unittest.IsolatedAsyncioTestCase):
    async def test_submitted_filename_is_reduced_to_safe_metadata(self) -> None:
        self.assertEqual(_safe_filename("../../payroll.csv"), "payroll.csv")
        self.assertEqual(_safe_filename(r"..\..\payroll.csv"), "payroll.csv")

    async def test_platform_rls_scope_is_not_available_to_arbitrary_callers(self) -> None:
        manager = DatabaseSessionManager(
            "postgresql+asyncpg://runtime:secret@localhost/task_management_test"
        )
        try:
            with self.assertRaises(ValueError):
                async with manager.session_for(principal_type="admin"):
                    pass
        finally:
            await manager.dispose()

    async def test_storage_uses_opaque_relative_keys_and_enforces_size(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            storage = LocalAttachmentStorage(Path(directory))
            upload = UploadFile(
                io.BytesIO(b"small payload"),
                filename="report.txt",
                headers=Headers({"content-type": "text/plain"}),
            )
            size = await storage.save("ab/opaque-key", upload, max_bytes=1024)
            self.assertEqual(size, len(b"small payload"))
            self.assertEqual(storage.resolve("ab/opaque-key").read_bytes(), b"small payload")

            oversized = UploadFile(
                io.BytesIO(b"x" * 32),
                filename="large.txt",
                headers=Headers({"content-type": "text/plain"}),
            )
            with self.assertRaises(BusinessRuleError):
                await storage.save("cd/another-key", oversized, max_bytes=10)
            self.assertFalse(storage.resolve("cd/another-key").exists())

    async def test_storage_rejects_path_traversal(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            storage = LocalAttachmentStorage(Path(directory))
            with self.assertRaises(ValueError):
                storage.resolve("../outside")
