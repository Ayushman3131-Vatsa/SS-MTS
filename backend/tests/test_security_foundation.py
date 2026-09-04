import asyncio
import json
import unittest
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.exceptions import RequestValidationError
from passlib.hash import bcrypt
from pydantic import ValidationError

from app.common.security import (
    hash_password,
    normalize_email,
    validate_password,
    verify_password_and_update,
)
from app.main import request_validation_error_handler
from app.tenant_management.models.enums import SubscriptionPlanCode
from app.task_management.schemas.comment import CommentCreateRequest
from app.tenant_management.schemas.tenant import TenantCreateRequest
from app.auth.schemas.user import UserCreateRequest
from app.auth.models.platform_admin import PlatformAdmin
from app.auth.models.platform_role import PlatformRole
from app.auth.models.platform_user_role import PlatformUserRole
import scripts.seed_platform_admin as seed_platform_admin
from scripts.seed_platform_admin import _prompt_for_password


REQUIRED_TENANT_PROFILE = {
    "tenant_code": "NORTHSTAR",
    "pan_number": "ABCDE1234F",
    "contact_name": "Avery Morgan",
    "contact_designation": "Operations Director",
    "contact_email": "avery@example.com",
}


class IdentityNormalizationTests(unittest.TestCase):
    def test_email_is_trimmed_and_casefolded_for_storage(self) -> None:
        self.assertEqual(
            normalize_email("  User.Name@Example.COM "),
            "user.name@example.com",
        )

class PasswordPolicyTests(unittest.TestCase):
    def test_strong_context_free_password_is_accepted(self) -> None:
        validate_password("Orbit!Sparrow42")

    def test_each_required_character_class_is_enforced(self) -> None:
        rejected = (
            "alllowercase!42",
            "ALLUPPERCASE!42",
            "NoDigitsHere!",
            "NoSpecialHere42",
        )
        for password in rejected:
            with self.subTest(password=password):
                with self.assertRaises(ValueError):
                    validate_password(password)

    def test_common_passwords_are_rejected(self) -> None:
        for password in ("Password123!", "P@ssword2026!"):
            with self.subTest(password=password), self.assertRaises(ValueError):
                validate_password(password)
        validate_password("Orbit!Sparrow42", org_name="Northstar Labs")
        with self.assertRaises(ValueError):
            validate_password("Northstar!Labs42", org_name="Northstar Labs")
        with self.assertRaises(ValueError):
            validate_password(
                "Ayush!Secure42",
                name="Ayush Sharma",
                email="ayush@example.com",
            )

    def test_short_and_identity_based_passwords_are_rejected(self) -> None:
        with self.assertRaises(ValueError):
            validate_password("Ab1!def")
        with self.assertRaises(ValueError):
            validate_password("J0hn!Secure42", username="john.smith", tenant_code="ACME")

    def test_new_hashes_are_argon2id(self) -> None:
        password_hash = hash_password("Orbit!Sparrow42")
        self.assertTrue(password_hash.startswith("$argon2id$"))
        verified, replacement = verify_password_and_update(
            "Orbit!Sparrow42",
            password_hash,
        )
        self.assertTrue(verified)
        self.assertIsNone(replacement)

    def test_legacy_bcrypt_hash_is_upgraded_after_verification(self) -> None:
        legacy_hash = bcrypt.using(rounds=4).hash("Legacy!Password42")
        verified, replacement = verify_password_and_update(
            "Legacy!Password42",
            legacy_hash,
        )
        self.assertTrue(verified)
        self.assertIsNotNone(replacement)
        self.assertTrue(replacement.startswith("$argon2id$"))


class CreationSchemaTests(unittest.TestCase):
    def test_tenant_creation_normalizes_identity_fields(self) -> None:
        payload = TenantCreateRequest(
            **{
                **REQUIRED_TENANT_PROFILE,
                "contact_name": "  Tenant Owner  ",
                "contact_email": "  OWNER@EXAMPLE.COM  ",
            },
            org_name="  Northstar Labs  ",
        )
        self.assertEqual(payload.org_name, "Northstar Labs")
        self.assertEqual(str(payload.contact_email), "owner@example.com")
        self.assertEqual(payload.contact_name, "Tenant Owner")
        self.assertEqual(
            payload.resolved_subscription_plan_code,
            SubscriptionPlanCode.FREE,
        )
        self.assertIsNone(payload.subscription_ends_at)

    def test_rich_tenant_registration_normalizes_profile_and_licenses(self) -> None:
        offering_id = uuid.uuid4()
        payload = TenantCreateRequest(
            org_name="  Northstar Labs  ",
            tenant_code="  northstar_01  ",
            legal_name="  Northstar Labs Private Limited  ",
            industry="  Technology  ",
            company_size="  51-200  ",
            tax_registration_number="  TAX-REG-123  ",
            pan_number="  abcde1234f  ",
            address_line_1="  1 Orbit Avenue  ",
            city="  Bengaluru  ",
            state_province="  Karnataka  ",
            country="  India  ",
            postal_code="  560001  ",
            contact_name="  Avery Morgan  ",
            contact_designation="  Operations Director  ",
            contact_email="  CONTACT@EXAMPLE.COM  ",
            contact_phone="  +91 99999 99999  ",
            alternate_contact_name="  Jordan Lee  ",
            alternate_contact_designation="  Finance Manager  ",
            alternate_contact_email="  JORDAN@EXAMPLE.COM  ",
            alternate_contact_phone="  +91 88888 88888  ",
            offering_ids=[offering_id],
        )
        self.assertEqual(payload.tenant_code, "NORTHSTAR_01")
        self.assertEqual(payload.legal_name, "Northstar Labs Private Limited")
        self.assertEqual(payload.tax_registration_number, "TAX-REG-123")
        self.assertEqual(payload.pan_number, "ABCDE1234F")
        self.assertEqual(payload.contact_designation, "Operations Director")
        self.assertEqual(payload.alternate_contact_designation, "Finance Manager")
        self.assertEqual(str(payload.alternate_contact_email), "jordan@example.com")
        self.assertEqual(str(payload.contact_email), "contact@example.com")
        self.assertEqual(payload.offering_ids, [offering_id])

    def test_tenant_registration_rejects_duplicate_bootstrap_roles(self) -> None:
        role_id = uuid.uuid4()
        with self.assertRaisesRegex(ValidationError, "must not contain duplicates"):
            TenantCreateRequest(
                **REQUIRED_TENANT_PROFILE,
                org_name="Northstar Labs",
                bootstrap_role_ids=[role_id, role_id],
            )

    def test_tenant_creation_accepts_stable_and_legacy_plan_codes(self) -> None:
        future_expiry = datetime.now(timezone.utc) + timedelta(days=30)
        stable = TenantCreateRequest(
            **REQUIRED_TENANT_PROFILE,
            org_name="Northstar Labs",
            subscription_plan_code=SubscriptionPlanCode.PRO,
            subscription_ends_at=future_expiry,
        )
        legacy = TenantCreateRequest(
            **REQUIRED_TENANT_PROFILE,
            org_name="Southstar Labs",
            subscription_plan="Professional",
            subscription_ends_at=future_expiry,
        )
        self.assertEqual(
            stable.resolved_subscription_plan_code,
            SubscriptionPlanCode.PRO,
        )
        self.assertEqual(
            legacy.resolved_subscription_plan_code,
            SubscriptionPlanCode.PRO,
        )

    def test_paid_plan_requires_a_future_expiry(self) -> None:
        common = {
            **REQUIRED_TENANT_PROFILE,
            "org_name": "Northstar Labs",
            "subscription_plan_code": SubscriptionPlanCode.BASIC,
        }
        with self.assertRaisesRegex(ValidationError, "require subscription_ends_at"):
            TenantCreateRequest(**common)
        with self.assertRaisesRegex(ValidationError, "must be in the future"):
            TenantCreateRequest(
                **common,
                subscription_ends_at=datetime.now(timezone.utc) - timedelta(days=1),
            )

    def test_free_plan_is_always_non_expiring(self) -> None:
        with self.assertRaisesRegex(
            ValidationError,
            "Free subscriptions must not specify subscription_ends_at",
        ):
            TenantCreateRequest(
                **REQUIRED_TENANT_PROFILE,
                org_name="Northstar Labs",
                subscription_plan_code=SubscriptionPlanCode.FREE,
                subscription_ends_at=datetime.now(timezone.utc) + timedelta(days=30),
            )

    def test_conflicting_stable_and_legacy_plan_fields_are_rejected(self) -> None:
        with self.assertRaisesRegex(ValidationError, "conflicts"):
            TenantCreateRequest(
                **REQUIRED_TENANT_PROFILE,
                org_name="Northstar Labs",
                subscription_plan_code=SubscriptionPlanCode.PRO,
                subscription_plan="Basic",
                subscription_ends_at=datetime.now(timezone.utc) + timedelta(days=30),
            )

    def test_user_creation_rejects_weak_passwords(self) -> None:
        with self.assertRaises(ValidationError):
            UserCreateRequest(
                name="Project Manager",
                username="project.manager",
                email="manager@example.com",
                password="weakpass",
                role="Project Manager",
            )

    def test_model_validation_response_never_echoes_password_input(self) -> None:
        plaintext_password = "AdminUser!Secret42"
        try:
            UserCreateRequest(
                name="Admin User",
                username="admin.user",
                email="admin@example.com",
                password=plaintext_password,
                role="Project Manager",
            )
        except ValidationError as exc:
            request_error = RequestValidationError(exc.errors())
        else:  # pragma: no cover - the contextual password must be rejected
            self.fail("Expected contextual password validation to fail")

        request = SimpleNamespace(url=SimpleNamespace(path="/users"))
        response = asyncio.run(
            request_validation_error_handler(request, request_error)  # type: ignore[arg-type]
        )
        response_body = response.body.decode("utf-8")

        self.assertEqual(response.status_code, 422)
        self.assertNotIn(plaintext_password, response_body)
        self.assertNotIn('"input"', response_body)
        self.assertIsInstance(json.loads(response_body)["detail"], list)

    def test_tenant_registration_requires_valid_pan_and_designation(self) -> None:
        base = {
            "tenant_code": "NORTHSTAR",
            "org_name": "Northstar Labs",
            "contact_name": "Avery Morgan",
            "contact_email": "avery@example.com",
        }
        with self.assertRaisesRegex(ValidationError, "pan_number"):
            TenantCreateRequest(**base, contact_designation="Director")
        with self.assertRaisesRegex(ValidationError, "contact_designation"):
            TenantCreateRequest(**base, pan_number="ABCDE1234F")
        with self.assertRaisesRegex(ValidationError, "string_pattern_mismatch"):
            TenantCreateRequest(
                **base,
                pan_number="INVALIDPAN",
                contact_designation="Director",
            )
        with self.assertRaisesRegex(ValidationError, "string_too_long"):
            TenantCreateRequest(
                **base,
                pan_number="ABCDE1234F",
                contact_designation="D" * 101,
            )

    def test_tenant_registration_rejects_legacy_identifier_fields(self) -> None:
        with self.assertRaisesRegex(ValidationError, "extra_forbidden"):
            TenantCreateRequest.model_validate(
                {
                    **REQUIRED_TENANT_PROFILE,
                    "org_name": "Northstar Labs",
                    "registration_number": "LEGACY-REG",
                    "tax_identifier": "LEGACY-TAX",
                }
            )

    def test_alternate_contact_requires_designation_with_all_other_fields(self) -> None:
        with self.assertRaisesRegex(
            ValidationError,
            "alternate contact name, designation, email, and phone",
        ):
            TenantCreateRequest(
                **REQUIRED_TENANT_PROFILE,
                org_name="Northstar Labs",
                alternate_contact_name="Jordan Lee",
                alternate_contact_email="jordan@example.com",
                alternate_contact_phone="+91 88888 88888",
            )

    def test_all_mutation_requests_reject_unexpected_fields(self) -> None:
        with self.assertRaises(ValidationError):
            CommentCreateRequest.model_validate(
                {
                    "comment_text": "Expected field",
                    "tenant_id": "must-not-be-client-controlled",
                }
            )


class SeedScriptTests(unittest.TestCase):
    @patch(
        "scripts.seed_platform_admin.getpass.getpass",
        side_effect=["Orbit!Sparrow42", "Orbit!Sparrow42"],
    )
    def test_seed_password_is_prompted_and_confirmed(self, prompt) -> None:
        self.assertEqual(_prompt_for_password(), "Orbit!Sparrow42")
        self.assertEqual(prompt.call_count, 2)

    @patch(
        "scripts.seed_platform_admin.getpass.getpass",
        side_effect=["Orbit!Sparrow42", "Different!Password42"],
    )
    def test_seed_password_confirmation_must_match(self, _prompt) -> None:
        with self.assertRaisesRegex(ValueError, "do not match"):
            _prompt_for_password()


class SeedScriptDatabaseTests(unittest.IsolatedAsyncioTestCase):
    @staticmethod
    def _session_manager(session):
        @asynccontextmanager
        async def managed_session():
            yield session

        return managed_session()

    async def test_seed_creates_admin_and_platform_role_assignment_atomically(self) -> None:
        role_id = uuid.uuid4()
        role = PlatformRole(
            id=role_id,
            role_code="PLATFORM_ADMIN",
            role_name="Platform Admin",
            is_active=True,
        )
        session = MagicMock()
        session.scalar = AsyncMock(side_effect=[role, None])
        session.commit = AsyncMock()

        with (
            patch.object(
                seed_platform_admin.db_manager,
                "session_for",
                return_value=self._session_manager(session),
            ),
            patch.object(seed_platform_admin, "hash_password", return_value="test-hash"),
            patch("builtins.print"),
        ):
            await seed_platform_admin._seed(
                "Initial Administrator",
                "admin@example.com",
                "Orbit!Sparrow42",
            )

        session.add_all.assert_called_once()
        admin, assignment = session.add_all.call_args.args[0]
        self.assertIsInstance(admin, PlatformAdmin)
        self.assertIsInstance(assignment, PlatformUserRole)
        self.assertEqual(assignment.admin_id, admin.admin_id)
        self.assertEqual(assignment.role_id, role_id)
        self.assertTrue(assignment.is_active)
        session.commit.assert_awaited_once()

    async def test_seed_repairs_existing_admin_without_changing_password(self) -> None:
        role = PlatformRole(
            id=uuid.uuid4(),
            role_code="PLATFORM_ADMIN",
            role_name="Platform Admin",
            is_active=True,
        )
        existing = PlatformAdmin(
            admin_id=uuid.uuid4(),
            name="Initial Administrator",
            email="admin@example.com",
            username="admin",
            password_hash="existing-hash",
        )
        session = MagicMock()
        session.scalar = AsyncMock(side_effect=[role, existing, None])
        session.commit = AsyncMock()

        with (
            patch.object(
                seed_platform_admin.db_manager,
                "session_for",
                return_value=self._session_manager(session),
            ),
            patch.object(seed_platform_admin, "hash_password") as hash_password_mock,
            patch.object(seed_platform_admin, "validate_password") as validate_password_mock,
            patch("builtins.print"),
        ):
            await seed_platform_admin._seed(
                existing.name,
                existing.email,
            )

        assignment = session.add.call_args.args[0]
        self.assertIsInstance(assignment, PlatformUserRole)
        self.assertEqual(assignment.admin_id, existing.admin_id)
        self.assertEqual(assignment.role_id, role.id)
        self.assertEqual(existing.password_hash, "existing-hash")
        hash_password_mock.assert_not_called()
        validate_password_mock.assert_not_called()
        session.commit.assert_awaited_once()

    async def test_seed_is_noop_when_existing_admin_already_has_role(self) -> None:
        role = PlatformRole(
            id=uuid.uuid4(),
            role_code="PLATFORM_ADMIN",
            role_name="Platform Admin",
            is_active=True,
        )
        existing = PlatformAdmin(
            admin_id=uuid.uuid4(),
            name="Initial Administrator",
            email="admin@example.com",
            username="admin",
            password_hash="existing-hash",
        )
        assignment = PlatformUserRole(
            id=uuid.uuid4(),
            admin_id=existing.admin_id,
            role_id=role.id,
            is_active=True,
        )
        session = MagicMock()
        session.scalar = AsyncMock(side_effect=[role, existing, assignment])
        session.commit = AsyncMock()

        with (
            patch.object(
                seed_platform_admin.db_manager,
                "session_for",
                return_value=self._session_manager(session),
            ),
            patch("builtins.print"),
        ):
            await seed_platform_admin._seed(
                existing.name,
                existing.email,
            )

        session.add.assert_not_called()
        session.add_all.assert_not_called()
        session.commit.assert_not_awaited()

    async def test_seed_reactivates_revoked_platform_admin_role(self) -> None:
        role = PlatformRole(
            id=uuid.uuid4(),
            role_code="PLATFORM_ADMIN",
            role_name="Platform Admin",
            is_active=True,
        )
        existing = PlatformAdmin(
            admin_id=uuid.uuid4(),
            name="Initial Administrator",
            email="admin@example.com",
            username="admin",
            password_hash="existing-hash",
        )
        assignment = PlatformUserRole(
            id=uuid.uuid4(),
            admin_id=existing.admin_id,
            role_id=role.id,
            is_active=False,
            revoked_at=datetime.now(timezone.utc),
            revoked_by=uuid.uuid4(),
        )
        session = MagicMock()
        session.scalar = AsyncMock(side_effect=[role, existing, assignment])
        session.commit = AsyncMock()

        with (
            patch.object(
                seed_platform_admin.db_manager,
                "session_for",
                return_value=self._session_manager(session),
            ),
            patch("builtins.print"),
        ):
            await seed_platform_admin._seed(existing.name, existing.email)

        self.assertTrue(assignment.is_active)
        self.assertIsNone(assignment.revoked_at)
        self.assertIsNone(assignment.revoked_by)
        session.commit.assert_awaited_once()

    async def test_seed_requires_migrated_platform_admin_role(self) -> None:
        session = MagicMock()
        session.scalar = AsyncMock(return_value=None)
        session.commit = AsyncMock()

        with patch.object(
            seed_platform_admin.db_manager,
            "session_for",
            return_value=self._session_manager(session),
        ):
            with self.assertRaisesRegex(ValueError, "alembic upgrade head"):
                await seed_platform_admin._seed(
                    "Initial Administrator",
                    "admin@example.com",
                    "Orbit!Sparrow42",
                )

        session.add.assert_not_called()
        session.add_all.assert_not_called()
        session.commit.assert_not_awaited()


if __name__ == "__main__":
    unittest.main()
