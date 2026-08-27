from enum import Enum


class TenantStatus(str, Enum):
    ACTIVE = "ACTIVE"
    SUSPENDED = "SUSPENDED"


class TenantOfferingStatus(str, Enum):
    ACTIVE = "ACTIVE"
    SUSPENDED = "SUSPENDED"
    EXPIRED = "EXPIRED"
    DEACTIVATED = "DEACTIVATED"


class DatabaseIsolationMode(str, Enum):
    SHARED = "SHARED"
    DEDICATED = "DEDICATED"


class DatabaseProvisioningState(str, Enum):
    PENDING = "PENDING"
    READY = "READY"
    FAILED = "FAILED"


class SubscriptionPlanCode(str, Enum):
    FREE = "FREE"
    BASIC = "BASIC"
    PRO = "PRO"
    ENTERPRISE = "ENTERPRISE"


class SubscriptionPlanStatus(str, Enum):
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"


class TenantSubscriptionStatus(str, Enum):
    ACTIVE = "ACTIVE"
    EXPIRED = "EXPIRED"
    CANCELLED = "CANCELLED"


class PlatformActivityType(str, Enum):
    TENANT_CREATED = "TENANT_CREATED"
    PLAN_CHANGED = "PLAN_CHANGED"
    TENANT_SUSPENDED = "TENANT_SUSPENDED"
    TENANT_REACTIVATED = "TENANT_REACTIVATED"
    DATABASE_ALLOCATION_READY = "DATABASE_ALLOCATION_READY"
    DATABASE_ALLOCATION_FAILED = "DATABASE_ALLOCATION_FAILED"
    TENANT_ACTIVATED = "TENANT_ACTIVATED"
    OFFERING_GRANTED = "OFFERING_GRANTED"
    OFFERING_SUSPENDED = "OFFERING_SUSPENDED"
    OFFERING_RESUMED = "OFFERING_RESUMED"
    OFFERING_DEACTIVATED = "OFFERING_DEACTIVATED"
    OFFERING_EXPIRED = "OFFERING_EXPIRED"
    OFFERING_CATALOG_CREATED = "OFFERING_CATALOG_CREATED"
    OFFERING_CATALOG_UPDATED = "OFFERING_CATALOG_UPDATED"
    OFFERING_CATALOG_ACTIVATED = "OFFERING_CATALOG_ACTIVATED"
    OFFERING_CATALOG_DEACTIVATED = "OFFERING_CATALOG_DEACTIVATED"
    OFFERING_CATALOG_DELETED = "OFFERING_CATALOG_DELETED"
    DEFAULT_TEMPLATE_CREATED = "DEFAULT_TEMPLATE_CREATED"
    DEFAULT_TEMPLATE_UPDATED = "DEFAULT_TEMPLATE_UPDATED"
    DEFAULT_ROLE_CREATED = "DEFAULT_ROLE_CREATED"
    DEFAULT_ROLE_UPDATED = "DEFAULT_ROLE_UPDATED"
    DEFAULT_ROLE_DELETED = "DEFAULT_ROLE_DELETED"


class PlatformActorType(str, Enum):
    PLATFORM_ADMIN = "PLATFORM_ADMIN"
    SYSTEM = "SYSTEM"


class ConfigTemplateType(str, Enum):
    EMAIL = "EMAIL"
    LETTER = "LETTER"
    NOTIFICATION = "NOTIFICATION"
    OTHER = "OTHER"


class ConfigCategoryStatus(str, Enum):
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"


LEGACY_SUBSCRIPTION_PLAN_CODES: dict[str, SubscriptionPlanCode] = {
    "free": SubscriptionPlanCode.FREE,
    "basic": SubscriptionPlanCode.BASIC,
    "pro": SubscriptionPlanCode.PRO,
    "professional": SubscriptionPlanCode.PRO,
    "enterprise": SubscriptionPlanCode.ENTERPRISE,
}


def parse_subscription_plan_code(value: str) -> SubscriptionPlanCode:
    """Resolve a legacy display name or a stable plan code.

    Keeping this mapping in one place prevents the compatibility request field
    and migration backfill from drifting semantically.
    """

    normalized = value.strip().casefold()
    try:
        return LEGACY_SUBSCRIPTION_PLAN_CODES[normalized]
    except KeyError:
        supported = ", ".join(code.value for code in SubscriptionPlanCode)
        raise ValueError(f"subscription plan must be one of: {supported}") from None

