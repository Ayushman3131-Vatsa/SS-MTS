import asyncio
import io
import tempfile
import unittest
import uuid
from datetime import date
from pathlib import Path
from unittest.mock import AsyncMock, patch

from pydantic import ValidationError
from starlette.datastructures import Headers, UploadFile

from app.core.config import Settings
from app.core.exceptions import BusinessRuleError
from app.db.base import Base
from app.db.session import DatabaseSessionManager
from app.main import app
from app.models.project import Project as LegacyProject
from app.models.task import Task as LegacyTask
from app.models.user import User
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
from app.modules.task_management.memberships import repository as membership_repository
from app.modules.task_management.memberships import service as membership_service
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

    def test_user_foreign_keys_resolve_to_user_accounts(self) -> None:
        expected_constraint_names = {
            "fk_project_pm",
            "fk_project_dm",
            "fk_task_assignee",
            "fk_task_tech_lead",
            "fk_task_func_lead",
            "fk_task_reporter",
            "fk_task_created_by",
            "fk_task_link_creator",
            "fk_project_member_user",
            "fk_project_member_added_by",
            "fk_comment_author",
            "fk_log_author",
            "fk_task_attachment_uploader",
            "fk_task_activity_actor",
        }
        resolved_constraint_names = set()

        for table in Base.metadata.tables.values():
            for constraint in table.foreign_key_constraints:
                if constraint.name not in expected_constraint_names:
                    continue
                targets = {element.column.table.name for element in constraint.elements}
                target_columns = {element.column.name for element in constraint.elements}
                self.assertEqual(targets, {"user_accounts"})
                self.assertEqual(target_columns, {"tenant_id", "id"})
                resolved_constraint_names.add(constraint.name)

        self.assertEqual(resolved_constraint_names, expected_constraint_names)

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


class TaskManagementMembershipTests(unittest.IsolatedAsyncioTestCase):
    async def test_member_lookup_uses_current_user_account_primary_key(self) -> None:
        tenant_id = uuid.uuid4()
        user_id = uuid.uuid4()
        user = User(
            id=user_id,
            tenant_id=tenant_id,
            email="member@example.test",
            password_hash="test-only",
            display_name="Project member",
            is_active=True,
        )
        db = AsyncMock()
        db.get.return_value = user

        result = await membership_repository.get_user(db, tenant_id, user_id)

        self.assertIs(result, user)
        db.get.assert_awaited_once_with(User, user_id)

    async def test_member_validation_loads_role_from_role_assignment(self) -> None:
        tenant_id = uuid.uuid4()
        user_id = uuid.uuid4()
        user = User(
            id=user_id,
            tenant_id=tenant_id,
            email="manager@example.test",
            password_hash="test-only",
            display_name="Project manager",
            is_active=True,
        )
        db = AsyncMock()

        with (
            patch.object(
                membership_service.repository,
                "get_user",
                AsyncMock(return_value=user),
            ),
            patch.object(
                membership_service,
                "get_active_role_name",
                AsyncMock(return_value="Project Manager"),
            ),
        ):
            result = await membership_service.validate_member_user(
                db,
                tenant_id,
                user_id,
                ProjectMemberRole.MANAGER,
            )

        self.assertIs(result, user)


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
