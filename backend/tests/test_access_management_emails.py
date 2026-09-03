from datetime import datetime, timezone
import unittest
from unittest.mock import AsyncMock, MagicMock, patch
import uuid

from app.access_control.platform.schemas import PlatformUserCreateRequest
from app.access_control.platform.users import service as platform_users_service
from app.auth.accounts import service as accounts_service
from app.auth.deps import Principal
from app.auth.models.platform_role import PlatformRole
from app.auth.schemas.user import UserCreateRequest
from app.tenant_management.models.tenant import Tenant


def _mock_refresh(user):
    if not getattr(user, "admin_id", None) and hasattr(user, "admin_id"):
        user.admin_id = uuid.uuid4()
    if not getattr(user, "id", None) and hasattr(user, "id"):
        user.id = uuid.uuid4()
    user.is_active = True
    if hasattr(user, "failed_login_count"):
        user.failed_login_count = 0
    if hasattr(user, "created_at") and user.created_at is None:
        user.created_at = datetime.now(timezone.utc)


class UserAccessEmailsIntegrationTests(unittest.IsolatedAsyncioTestCase):
    async def test_create_platform_user_with_role_triggers_email(self) -> None:
        db = AsyncMock()
        actor_id = uuid.uuid4()
        role_id = uuid.uuid4()

        payload = PlatformUserCreateRequest(
            name="Priya Sharma",
            username="priya_admin",
            email="priya@example.com",
            role_ids=[role_id],
        )

        role = PlatformRole(
            id=role_id,
            role_code="SUPER_ADMIN",
            role_name="Super Admin",
            description="Full admin access",
            module_scope="platform",
            is_system=False,
            is_active=True,
            created_at=datetime.now(timezone.utc),
        )

        existing_mock = MagicMock()
        existing_mock.scalar_one_or_none.return_value = None
        db.execute = AsyncMock(return_value=existing_mock)
        db.refresh.side_effect = _mock_refresh

        with (
            patch("app.access_control.platform.users.service.normalize_email", return_value="priya@example.com"),
            patch("app.access_control.platform.users.service.reserve_platform_username", return_value="priya_admin"),
            patch("app.access_control.platform.users.service.load_platform_roles", return_value=[role]),
            patch("app.access_control.platform.users.service.send_platform_templated_email", new_callable=AsyncMock) as mock_send_email,
        ):
            result = await platform_users_service.create_platform_user(
                db,
                actor_id=actor_id,
                payload=payload,
            )

            self.assertEqual(result.email, "priya@example.com")
            await accounts_service.asyncio.sleep(0.01)
            mock_send_email.assert_awaited()

    async def test_create_tenant_user_triggers_email(self) -> None:
        db = AsyncMock()
        tenant_id = uuid.uuid4()
        user_id = uuid.uuid4()
        principal = Principal(
            type="user",
            id=user_id,
            email="admin@tenant.example",
            tenant_id=tenant_id,
            role="Tenant Admin",
            roles=("Tenant Admin",),
        )
        tenant = Tenant(
            tenant_id=tenant_id,
            org_name="Acme Corp",
            tenant_code="ACME",
            status="ACTIVE",
        )

        payload = UserCreateRequest(
            name="John Doe",
            username="john_doe",
            email="john@example.com",
            role_ids=[],
        )

        db.refresh.side_effect = _mock_refresh

        with (
            patch("app.auth.accounts.service.reserve_new_user_email", return_value="john@example.com"),
            patch("app.auth.accounts.service.reserve_tenant_username", return_value="john_doe"),
            patch("app.auth.accounts.service.send_templated_email", new_callable=AsyncMock) as mock_send_email,
        ):
            db.get.return_value = tenant

            result = await accounts_service.create_user(
                db,
                principal=principal,
                payload=payload,
            )

            self.assertEqual(result.view.account.display_name, "John Doe")
            await accounts_service.asyncio.sleep(0.01)
            mock_send_email.assert_awaited()
