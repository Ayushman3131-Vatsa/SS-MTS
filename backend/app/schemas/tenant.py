import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Self

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator

from app.core.security import (
    WORKSPACE_SLUG_PATTERN,
    normalize_email,
    normalize_workspace_slug,
    validate_password,
)
from app.models.enums import (
    DatabaseIsolationMode,
    DatabaseProvisioningState,
    SubscriptionPlanCode,
    TenantStatus,
    parse_subscription_plan_code,
)
from app.schemas.base import StrictRequestModel


class TenantOfferingGrantRequest(StrictRequestModel):
    offering_id: uuid.UUID
    starts_at: datetime
    ends_at: datetime
    expected_tenant_version: int = Field(default=1, ge=1)
    reason: str | None = Field(default=None, max_length=1000)

    @field_validator("reason")
    @classmethod
    def normalize_reason(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        return value or None

    @model_validator(mode="after")
    def validate_window(self) -> Self:
        for field_name, value in (("starts_at", self.starts_at), ("ends_at", self.ends_at)):
            if value.tzinfo is None or value.utcoffset() is None:
                raise ValueError(f"{field_name} must include a timezone")
            if value.utcoffset() != timezone.utc.utcoffset(value):
                raise ValueError(f"{field_name} must be expressed in UTC")
        if self.ends_at <= self.starts_at:
            raise ValueError("ends_at must be later than starts_at")
        if self.ends_at <= datetime.now(timezone.utc):
            raise ValueError("ends_at must be in the future")
        return self


class TenantCreateRequest(StrictRequestModel):
    org_name: str = Field(min_length=1, max_length=255)
    tenant_code: str | None = Field(
        default=None,
        min_length=2,
        max_length=30,
        pattern=r"^[A-Z0-9][A-Z0-9_-]*$",
    )
    workspace_slug: str | None = Field(
        default=None,
        min_length=3,
        max_length=63,
        pattern=WORKSPACE_SLUG_PATTERN,
    )
    subscription_plan_code: SubscriptionPlanCode | None = Field(default=None)
    subscription_ends_at: datetime | None = Field(default=None)
    subscription_plan: str | None = Field(
        default=None,
        max_length=50,
        deprecated=True,
        description=(
            "Deprecated compatibility field. Use subscription_plan_code; "
            "accepted for one release."
        ),
    )
    status: TenantStatus = TenantStatus.ACTIVE
    database_mode: DatabaseIsolationMode = DatabaseIsolationMode.SHARED
    legal_name: str | None = Field(default=None, min_length=1, max_length=255)
    industry: str | None = Field(default=None, min_length=1, max_length=100)
    company_size: str | None = Field(default=None, min_length=1, max_length=50)
    website: str | None = Field(
        default=None,
        max_length=500,
        pattern=r"^https?://",
    )
    registration_number: str | None = Field(default=None, max_length=100)
    tax_identifier: str | None = Field(default=None, max_length=100)
    address_line_1: str | None = Field(default=None, min_length=1, max_length=255)
    address_line_2: str | None = Field(default=None, max_length=255)
    city: str | None = Field(default=None, min_length=1, max_length=100)
    state_province: str | None = Field(default=None, min_length=1, max_length=100)
    country: str | None = Field(default=None, min_length=1, max_length=100)
    postal_code: str | None = Field(default=None, min_length=1, max_length=30)
    contact_name: str | None = Field(default=None, min_length=1, max_length=255)
    contact_email: EmailStr | None = Field(default=None, max_length=254)
    contact_phone: str | None = Field(
        default=None,
        min_length=5,
        max_length=40,
        pattern=r"^[0-9+().\-\s]+$",
    )
    alternate_contact_name: str | None = Field(default=None, min_length=1, max_length=255)
    alternate_contact_email: EmailStr | None = Field(default=None, max_length=254)
    alternate_contact_phone: str | None = Field(
        default=None,
        min_length=5,
        max_length=40,
        pattern=r"^[0-9+().\-\s]+$",
    )
    offering_ids: list[uuid.UUID] = Field(default_factory=list, max_length=50)
    offering_grants: list[TenantOfferingGrantRequest] = Field(default_factory=list, max_length=50)
    tenant_admin_name: str = Field(min_length=1, max_length=255)
    tenant_admin_email: EmailStr = Field(max_length=254)
    tenant_admin_password: str = Field(min_length=12, max_length=128)

    @field_validator(
        "org_name",
        "tenant_admin_name",
    )
    @classmethod
    def normalize_text(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("must not be blank")
        return normalized

    @field_validator(
        "website",
        "registration_number",
        "tax_identifier",
        "address_line_2",
    )
    @classmethod
    def normalize_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None

    @field_validator(
        "legal_name",
        "industry",
        "company_size",
        "address_line_1",
        "city",
        "state_province",
        "country",
        "postal_code",
        "contact_name",
        "contact_phone",
        "alternate_contact_name",
        "alternate_contact_phone",
    )
    @classmethod
    def normalize_optional_required_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            raise ValueError("must not be blank")
        return normalized

    @field_validator("tenant_code", mode="before")
    @classmethod
    def normalize_tenant_code(cls, value: object) -> object:
        return value.strip().upper() if isinstance(value, str) else value

    @field_validator("subscription_plan")
    @classmethod
    def normalize_legacy_subscription_plan(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            raise ValueError("must not be blank")
        return normalized

    @field_validator("workspace_slug", mode="before")
    @classmethod
    def normalize_explicit_slug(cls, value: object) -> object:
        if not isinstance(value, str):
            return value
        return value.strip().lower()

    @field_validator(
        "tenant_admin_email",
        "contact_email",
        "alternate_contact_email",
        mode="before",
    )
    @classmethod
    def normalize_admin_email(cls, value: object) -> object:
        return normalize_email(value) if isinstance(value, str) else value

    @model_validator(mode="after")
    def enforce_creation_policies(self) -> Self:
        if len(set(self.offering_ids)) != len(self.offering_ids):
            raise ValueError("offering_ids must not contain duplicates")
        grant_ids = [grant.offering_id for grant in self.offering_grants]
        if len(set(grant_ids)) != len(grant_ids):
            raise ValueError("offering_grants must not contain duplicates")
        if self.offering_ids and self.offering_grants:
            raise ValueError("Use offering_grants instead of offering_ids")
        alternate_contact_values = (
            self.alternate_contact_name,
            self.alternate_contact_email,
            self.alternate_contact_phone,
        )
        if any(value is not None for value in alternate_contact_values) and not all(
            value is not None for value in alternate_contact_values
        ):
            raise ValueError(
                "alternate contact name, email, and phone must be provided together"
            )
        plan_code = self.resolved_subscription_plan_code
        if self.subscription_ends_at is not None:
            if (
                self.subscription_ends_at.tzinfo is None
                or self.subscription_ends_at.utcoffset() is None
            ):
                raise ValueError("subscription_ends_at must include a timezone")
            if self.subscription_ends_at <= datetime.now(timezone.utc):
                raise ValueError("subscription_ends_at must be in the future")
        if (
            plan_code is not SubscriptionPlanCode.FREE
            and self.subscription_ends_at is None
        ):
            raise ValueError("paid subscription plans require subscription_ends_at")
        if (
            plan_code is SubscriptionPlanCode.FREE
            and self.subscription_ends_at is not None
        ):
            raise ValueError("Free subscriptions must not specify subscription_ends_at")

        validate_password(
            self.tenant_admin_password,
            email=str(self.tenant_admin_email),
            name=self.tenant_admin_name,
            org_name=self.org_name,
            workspace_slug=self.workspace_slug or normalize_workspace_slug(self.org_name),
        )
        return self

    @property
    def resolved_subscription_plan_code(self) -> SubscriptionPlanCode:
        # Pydantic intentionally emits a DeprecationWarning when a field
        # marked deprecated is accessed as an attribute. Internal
        # compatibility handling should not warn on every valid request.
        legacy_plan = self.__dict__.get("subscription_plan")
        legacy_code = (
            parse_subscription_plan_code(legacy_plan)
            if legacy_plan is not None
            else None
        )
        if (
            self.subscription_plan_code is not None
            and legacy_code is not None
            and self.subscription_plan_code is not legacy_code
        ):
            raise ValueError(
                "subscription_plan conflicts with subscription_plan_code"
            )
        return self.subscription_plan_code or legacy_code or SubscriptionPlanCode.FREE


class OfferingResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    offering_id: uuid.UUID
    code: str
    display_name: str
    description: str
    icon_key: str
    route_slug: str
    sort_order: int


class TenantOfferingResponse(OfferingResponse):
    entitlement_id: uuid.UUID
    status: str
    starts_at: datetime
    ends_at: datetime | None
    suspended_at: datetime | None
    deactivated_at: datetime | None
    reason: str | None
    version: int
    created_at: datetime
    updated_at: datetime


class TenantOfferingEventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    event_id: uuid.UUID
    entitlement_id: uuid.UUID
    tenant_id: uuid.UUID
    event_type: str
    actor_admin_id: uuid.UUID | None
    occurred_at: datetime
    old_value: dict | None
    new_value: dict | None


class OfferingCatalogResponse(OfferingResponse):
    status: str


class TenantOfferingActionRequest(StrictRequestModel):
    expected_version: int = Field(ge=1)
    reason: str | None = Field(default=None, max_length=1000)

    @field_validator("reason")
    @classmethod
    def normalize_reason(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        return value or None


class TenantOfferingRemovalRequest(StrictRequestModel):
    expected_version: int = Field(ge=1)
    reason: str = Field(min_length=1, max_length=1000)

    @field_validator("reason")
    @classmethod
    def normalize_reason(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("must not be blank")
        return value


class TenantStatusActionRequest(StrictRequestModel):
    expected_version: int = Field(ge=1)
    reason: str | None = Field(default=None, max_length=1000)

    @field_validator("reason")
    @classmethod
    def normalize_reason(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        return value or None


class SubscriptionPlanOptionResponse(BaseModel):
    code: SubscriptionPlanCode
    display_name: str
    price: Decimal | None
    currency: str | None
    billing_interval: str | None
    max_users: int | None
    requires_end_date: bool


class RegistrationDefaultsResponse(BaseModel):
    subscription_plan_code: SubscriptionPlanCode
    status: TenantStatus
    database_mode: DatabaseIsolationMode


class TenantRegistrationOptionsResponse(BaseModel):
    plans: list[SubscriptionPlanOptionResponse]
    offerings: list[OfferingResponse]
    statuses: list[TenantStatus]
    database_modes: list[DatabaseIsolationMode]
    defaults: RegistrationDefaultsResponse


class TenantResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    tenant_id: uuid.UUID
    org_name: str
    tenant_code: str
    workspace_slug: str
    legal_name: str | None
    industry: str | None
    company_size: str | None
    website: str | None
    registration_number: str | None
    tax_identifier: str | None
    address_line_1: str | None
    address_line_2: str | None
    city: str | None
    state_province: str | None
    country: str | None
    postal_code: str | None
    contact_name: str | None
    contact_email: str | None
    contact_phone: str | None
    alternate_contact_name: str | None
    alternate_contact_email: str | None
    alternate_contact_phone: str | None
    subscription_plan: str
    subscription_plan_code: SubscriptionPlanCode
    subscription_ends_at: datetime | None
    status: TenantStatus
    database_mode: DatabaseIsolationMode
    database_provisioning_state: DatabaseProvisioningState
    user_count: int
    offerings: list[TenantOfferingResponse]
    created_by_admin_id: uuid.UUID
    created_at: datetime
    updated_at: datetime
    version: int


class TenantListResponse(BaseModel):
    items: list[TenantResponse]
    page: int
    page_size: int
    total: int
