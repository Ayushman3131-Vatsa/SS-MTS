import asyncio
import json
import unittest
import uuid
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import patch

from fastapi.exceptions import RequestValidationError
from passlib.hash import bcrypt
from pydantic import ValidationError

from app.core.security import (
    hash_password,
    normalize_email,
    normalize_workspace_slug,
    validate_password,
    verify_password_and_update,
)
from app.main import request_validation_error_handler
from app.models.enums import SubscriptionPlanCode
from app.schemas.comment import CommentCreateRequest
from app.schemas.tenant import TenantCreateRequest
from app.schemas.user import UserCreateRequest
from scripts.seed_platform_admin import _prompt_for_password


class IdentityNormalizationTests(unittest.TestCase):
    def test_email_is_trimmed_and_casefolded_for_storage(self) -> None:
        self.assertEqual(
            normalize_email("  User.Name@Example.COM "),
            "user.name@example.com",
        )

    def test_workspace_slug_is_deterministic_and_url_safe(self) -> None:
        self.assertEqual(
            normalize_workspace_slug(" Northstar Labs & Engineering "),
            "northstar-labs-engineering",
        )
        self.assertEqual(normalize_workspace_slug("AI"), "ai-org")


class PasswordPolicyTests(unittest.TestCase):
    def test_strong_context_free_password_is_accepted(self) -> None:
        validate_password("Orbit!Sparrow42")

    def test_each_required_character_class_is_enforced(self) -> None:
        rejected = (
            "short!A1",
            "alllowercase!42",
            "ALLUPPERCASE!42",
            "NoDigitsHere!",
            "NoSpecialHere42",
        )
        for password in rejected:
            with self.subTest(password=password):
                with self.assertRaises(ValueError):
                    validate_password(password)

    def test_common_and_contextual_passwords_are_rejected(self) -> None:
        for password in ("Password123!", "P@ssword2026!"):
            with self.subTest(password=password), self.assertRaises(ValueError):
                validate_password(password)
        with self.assertRaises(ValueError):
            validate_password(
                "Northstar!Labs42",
                org_name="Northstar Labs",
                workspace_slug="northstar-labs",
            )
        with self.assertRaises(ValueError):
            validate_password(
                "Ayush!Secure42",
                name="Ayush Sharma",
                email="ayush@example.com",
            )

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
            org_name="  Northstar Labs  ",
            workspace_slug="  NORTHSTAR-LABS  ",
            tenant_admin_name="  Tenant Owner  ",
            tenant_admin_email="  OWNER@EXAMPLE.COM  ",
            tenant_admin_password="Ridge!Harbor72",
        )
        self.assertEqual(payload.org_name, "Northstar Labs")
        self.assertEqual(payload.workspace_slug, "northstar-labs")
        self.assertEqual(str(payload.tenant_admin_email), "owner@example.com")
        self.assertEqual(payload.tenant_admin_name, "Tenant Owner")
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
            address_line_1="  1 Orbit Avenue  ",
            city="  Bengaluru  ",
            state_province="  Karnataka  ",
            country="  India  ",
            postal_code="  560001  ",
            contact_name="  Avery Morgan  ",
            contact_email="  CONTACT@EXAMPLE.COM  ",
            contact_phone="  +91 99999 99999  ",
            offering_ids=[offering_id],
            tenant_admin_name="Tenant Owner",
            tenant_admin_email="owner@example.com",
            tenant_admin_password="Ridge!Harbor72",
        )
        self.assertEqual(payload.tenant_code, "NORTHSTAR_01")
        self.assertEqual(payload.legal_name, "Northstar Labs Private Limited")
        self.assertEqual(str(payload.contact_email), "contact@example.com")
        self.assertEqual(payload.offering_ids, [offering_id])

    def test_tenant_registration_rejects_duplicate_offerings(self) -> None:
        offering_id = uuid.uuid4()
        with self.assertRaisesRegex(ValidationError, "must not contain duplicates"):
            TenantCreateRequest(
                org_name="Northstar Labs",
                offering_ids=[offering_id, offering_id],
                tenant_admin_name="Tenant Owner",
                tenant_admin_email="owner@example.com",
                tenant_admin_password="Ridge!Harbor72",
            )

    def test_tenant_creation_accepts_stable_and_legacy_plan_codes(self) -> None:
        future_expiry = datetime.now(timezone.utc) + timedelta(days=30)
        stable = TenantCreateRequest(
            org_name="Northstar Labs",
            subscription_plan_code=SubscriptionPlanCode.PRO,
            subscription_ends_at=future_expiry,
            tenant_admin_name="Tenant Owner",
            tenant_admin_email="owner@example.com",
            tenant_admin_password="Ridge!Harbor72",
        )
        legacy = TenantCreateRequest(
            org_name="Southstar Labs",
            subscription_plan="Professional",
            subscription_ends_at=future_expiry,
            tenant_admin_name="Tenant Owner",
            tenant_admin_email="owner@example.com",
            tenant_admin_password="Ridge!Harbor72",
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
            "org_name": "Northstar Labs",
            "subscription_plan_code": SubscriptionPlanCode.BASIC,
            "tenant_admin_name": "Tenant Owner",
            "tenant_admin_email": "owner@example.com",
            "tenant_admin_password": "Ridge!Harbor72",
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
                org_name="Northstar Labs",
                subscription_plan_code=SubscriptionPlanCode.FREE,
                subscription_ends_at=datetime.now(timezone.utc) + timedelta(days=30),
                tenant_admin_name="Tenant Owner",
                tenant_admin_email="owner@example.com",
                tenant_admin_password="Ridge!Harbor72",
            )

    def test_conflicting_stable_and_legacy_plan_fields_are_rejected(self) -> None:
        with self.assertRaisesRegex(ValidationError, "conflicts"):
            TenantCreateRequest(
                org_name="Northstar Labs",
                subscription_plan_code=SubscriptionPlanCode.PRO,
                subscription_plan="Basic",
                subscription_ends_at=datetime.now(timezone.utc) + timedelta(days=30),
                tenant_admin_name="Tenant Owner",
                tenant_admin_email="owner@example.com",
                tenant_admin_password="Ridge!Harbor72",
            )

    def test_tenant_and_user_creation_reject_weak_passwords(self) -> None:
        with self.assertRaises(ValidationError):
            TenantCreateRequest(
                org_name="Northstar Labs",
                tenant_admin_name="Tenant Owner",
                tenant_admin_email="owner@example.com",
                tenant_admin_password="weakpass",
            )
        with self.assertRaises(ValidationError):
            UserCreateRequest(
                name="Project Manager",
                email="manager@example.com",
                password="weakpass",
                role="Project Manager",
            )

    def test_model_validation_response_never_echoes_password_input(self) -> None:
        plaintext_password = "Northstar!Secret42"
        try:
            TenantCreateRequest(
                org_name="Northstar Labs",
                workspace_slug="northstar-labs",
                tenant_admin_name="Admin User",
                tenant_admin_email="admin@example.com",
                tenant_admin_password=plaintext_password,
            )
        except ValidationError as exc:
            request_error = RequestValidationError(exc.errors())
        else:  # pragma: no cover - the contextual password must be rejected
            self.fail("Expected contextual password validation to fail")

        request = SimpleNamespace(url=SimpleNamespace(path="/tenants"))
        response = asyncio.run(
            request_validation_error_handler(request, request_error)  # type: ignore[arg-type]
        )
        response_body = response.body.decode("utf-8")

        self.assertEqual(response.status_code, 422)
        self.assertNotIn(plaintext_password, response_body)
        self.assertNotIn('"input"', response_body)
        self.assertIsInstance(json.loads(response_body)["detail"], list)

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


if __name__ == "__main__":
    unittest.main()
