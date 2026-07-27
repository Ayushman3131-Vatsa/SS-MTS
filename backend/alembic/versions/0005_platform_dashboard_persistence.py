"""add platform dashboard persistence

Revision ID: 0005
Revises: 0004
Create Date: 2026-07-23
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0005"
down_revision: Union[str, None] = "0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "tenants",
        sa.Column(
            "status",
            sa.String(length=20),
            server_default=sa.text("'ACTIVE'"),
            nullable=False,
        ),
    )
    op.add_column(
        "tenants",
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
    )
    op.create_check_constraint(
        "check_tenants_status",
        "tenants",
        "status IN ('ACTIVE', 'SUSPENDED')",
    )
    op.create_index(
        "ix_tenants_status_created_at",
        "tenants",
        ["status", "created_at"],
        unique=False,
    )
    op.alter_column(
        "tenants",
        "subscription_plan",
        existing_type=sa.String(length=50),
        existing_nullable=False,
        server_default=sa.text("'Free'"),
    )

    op.create_table(
        "subscription_plans",
        sa.Column(
            "plan_id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("uuid_generate_v4()"),
            nullable=False,
        ),
        sa.Column("code", sa.String(length=20), nullable=False),
        sa.Column("display_name", sa.String(length=100), nullable=False),
        sa.Column("price", sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column("currency", sa.String(length=3), nullable=True),
        sa.Column("billing_interval", sa.String(length=20), nullable=True),
        sa.Column("max_users", sa.Integer(), nullable=True),
        sa.Column(
            "features_json",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.String(length=20),
            server_default=sa.text("'ACTIVE'"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "code IN ('FREE', 'BASIC', 'PRO', 'ENTERPRISE')",
            name="check_subscription_plans_code",
        ),
        sa.CheckConstraint(
            "status IN ('ACTIVE', 'INACTIVE')",
            name="check_subscription_plans_status",
        ),
        sa.CheckConstraint(
            "price IS NULL OR price >= 0",
            name="check_subscription_plans_price",
        ),
        sa.CheckConstraint(
            "max_users IS NULL OR max_users > 0",
            name="check_subscription_plans_max_users",
        ),
        sa.PrimaryKeyConstraint("plan_id", name="pk_subscription_plans"),
        sa.UniqueConstraint("code", name="uq_subscription_plans_code"),
    )
    op.execute(
        """
        INSERT INTO subscription_plans
            (plan_id, code, display_name, price, currency,
             billing_interval, max_users, features_json, status)
        VALUES
            ('00000000-0000-4000-8000-000000000001', 'FREE', 'Free',
             0.00, 'USD', 'MONTHLY', NULL, '{}'::jsonb, 'ACTIVE'),
            ('00000000-0000-4000-8000-000000000002', 'BASIC', 'Basic',
             NULL, 'USD', 'MONTHLY', NULL, '{}'::jsonb, 'ACTIVE'),
            ('00000000-0000-4000-8000-000000000003', 'PRO', 'Professional',
             NULL, 'USD', 'MONTHLY', NULL, '{}'::jsonb, 'ACTIVE'),
            ('00000000-0000-4000-8000-000000000004', 'ENTERPRISE', 'Enterprise',
             NULL, 'USD', 'CUSTOM', NULL, '{}'::jsonb, 'ACTIVE')
        """
    )

    # Refuse to guess when historical free-text plan data cannot be mapped to
    # the stable catalog. PostgreSQL rolls the complete revision back, leaving
    # operators able to correct the source row and retry safely.
    op.execute(
        """
        DO $$
        DECLARE
            unknown_plans TEXT;
        BEGIN
            SELECT string_agg(DISTINCT subscription_plan, ', ' ORDER BY subscription_plan)
            INTO unknown_plans
            FROM tenants
            WHERE lower(btrim(subscription_plan)) NOT IN (
                'free', 'basic', 'pro', 'professional', 'enterprise'
            );

            IF unknown_plans IS NOT NULL THEN
                RAISE EXCEPTION
                    'Cannot migrate tenants.subscription_plan: unknown values: %',
                    unknown_plans
                    USING ERRCODE = '23514';
            END IF;
        END
        $$;
        """
    )

    op.create_table(
        "tenant_subscriptions",
        sa.Column(
            "subscription_id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("uuid_generate_v4()"),
            nullable=False,
        ),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("plan_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "starts_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "is_current",
            sa.Boolean(),
            server_default=sa.text("true"),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.String(length=20),
            server_default=sa.text("'ACTIVE'"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "status IN ('ACTIVE', 'EXPIRED', 'CANCELLED')",
            name="check_tenant_subscriptions_status",
        ),
        sa.CheckConstraint(
            "ends_at IS NULL OR ends_at > starts_at",
            name="check_tenant_subscriptions_date_order",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.tenant_id"],
            name="fk_tenant_subscriptions_tenant_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["plan_id"],
            ["subscription_plans.plan_id"],
            name="fk_tenant_subscriptions_plan_id",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint(
            "subscription_id",
            name="pk_tenant_subscriptions",
        ),
    )
    op.create_index(
        "uq_tenant_subscriptions_current",
        "tenant_subscriptions",
        ["tenant_id"],
        unique=True,
        postgresql_where=sa.text("is_current IS TRUE"),
    )
    op.create_index(
        "ix_tenant_subscriptions_current_plan",
        "tenant_subscriptions",
        ["is_current", "plan_id"],
        unique=False,
    )
    op.create_index(
        "ix_tenant_subscriptions_ends_at",
        "tenant_subscriptions",
        ["ends_at"],
        unique=False,
    )
    op.execute(
        """
        INSERT INTO tenant_subscriptions
            (subscription_id, tenant_id, plan_id, starts_at, ends_at,
             is_current, status, created_at, updated_at)
        SELECT
            uuid_generate_v4(),
            tenant.tenant_id,
            plan.plan_id,
            tenant.created_at,
            NULL,
            true,
            'ACTIVE',
            tenant.created_at,
            CURRENT_TIMESTAMP
        FROM tenants AS tenant
        JOIN subscription_plans AS plan
          ON plan.code = CASE lower(btrim(tenant.subscription_plan))
              WHEN 'free' THEN 'FREE'
              WHEN 'basic' THEN 'BASIC'
              WHEN 'pro' THEN 'PRO'
              WHEN 'professional' THEN 'PRO'
              WHEN 'enterprise' THEN 'ENTERPRISE'
          END
        """
    )

    op.create_table(
        "tenant_database_allocations",
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "mode",
            sa.String(length=20),
            server_default=sa.text("'SHARED'"),
            nullable=False,
        ),
        sa.Column(
            "provisioning_state",
            sa.String(length=20),
            server_default=sa.text("'READY'"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column("ready_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "mode IN ('SHARED', 'DEDICATED')",
            name="check_tenant_database_allocations_mode",
        ),
        sa.CheckConstraint(
            "provisioning_state IN ('PENDING', 'READY', 'FAILED')",
            name="check_tenant_database_allocations_state",
        ),
        sa.CheckConstraint(
            "(provisioning_state = 'READY' AND ready_at IS NOT NULL) "
            "OR (provisioning_state <> 'READY' AND ready_at IS NULL)",
            name="check_tenant_database_allocations_ready_at",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.tenant_id"],
            name="fk_tenant_database_allocations_tenant_id",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(
            "tenant_id",
            name="pk_tenant_database_allocations",
        ),
    )
    op.create_index(
        "ix_tenant_database_allocations_dashboard",
        "tenant_database_allocations",
        ["mode", "provisioning_state"],
        unique=False,
    )
    op.execute(
        """
        INSERT INTO tenant_database_allocations
            (tenant_id, mode, provisioning_state, created_at, updated_at, ready_at)
        SELECT
            tenant_id,
            'SHARED',
            'READY',
            created_at,
            CURRENT_TIMESTAMP,
            created_at
        FROM tenants
        """
    )

    op.create_table(
        "platform_activity_events",
        sa.Column(
            "activity_id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("uuid_generate_v4()"),
            nullable=False,
        ),
        sa.Column("event_type", sa.String(length=50), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("tenant_name_snapshot", sa.String(length=255), nullable=False),
        sa.Column("actor_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("actor_type", sa.String(length=30), nullable=False),
        sa.Column(
            "occurred_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("idempotency_key", sa.String(length=255), nullable=False),
        sa.CheckConstraint(
            "event_type IN ("
            "'TENANT_CREATED', 'PLAN_CHANGED', 'TENANT_SUSPENDED', "
            "'TENANT_REACTIVATED', 'DATABASE_ALLOCATION_READY', "
            "'DATABASE_ALLOCATION_FAILED')",
            name="check_platform_activity_events_type",
        ),
        sa.CheckConstraint(
            "actor_type IN ('PLATFORM_ADMIN', 'SYSTEM')",
            name="check_platform_activity_events_actor_type",
        ),
        sa.CheckConstraint(
            "(actor_type = 'PLATFORM_ADMIN' AND actor_id IS NOT NULL) "
            "OR (actor_type = 'SYSTEM' AND actor_id IS NULL)",
            name="check_platform_activity_events_actor",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.tenant_id"],
            name="fk_platform_activity_events_tenant_id",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint(
            "activity_id",
            name="pk_platform_activity_events",
        ),
        sa.UniqueConstraint(
            "idempotency_key",
            name="uq_platform_activity_events_idempotency_key",
        ),
    )
    op.create_index(
        "ix_platform_activity_events_occurred_at",
        "platform_activity_events",
        ["occurred_at"],
        unique=False,
    )
    op.create_index(
        "ix_platform_activity_events_tenant_occurred_at",
        "platform_activity_events",
        ["tenant_id", "occurred_at"],
        unique=False,
    )
    op.execute(
        """
        INSERT INTO platform_activity_events
            (activity_id, event_type, tenant_id, tenant_name_snapshot,
             actor_id, actor_type, occurred_at, metadata, idempotency_key)
        SELECT
            uuid_generate_v4(),
            'TENANT_CREATED',
            tenant.tenant_id,
            tenant.org_name,
            tenant.created_by_admin_id,
            'PLATFORM_ADMIN',
            tenant.created_at,
            jsonb_build_object(
                'workspace_slug', tenant.workspace_slug,
                'subscription_plan_code', plan.code
            ),
            'tenant-created:' || tenant.tenant_id::text
        FROM tenants AS tenant
        JOIN tenant_subscriptions AS subscription
          ON subscription.tenant_id = tenant.tenant_id
         AND subscription.is_current IS TRUE
        JOIN subscription_plans AS plan
          ON plan.plan_id = subscription.plan_id
        """
    )


def downgrade() -> None:
    op.drop_index(
        "ix_platform_activity_events_tenant_occurred_at",
        table_name="platform_activity_events",
    )
    op.drop_index(
        "ix_platform_activity_events_occurred_at",
        table_name="platform_activity_events",
    )
    op.drop_table("platform_activity_events")

    op.drop_index(
        "ix_tenant_database_allocations_dashboard",
        table_name="tenant_database_allocations",
    )
    op.drop_table("tenant_database_allocations")

    op.drop_index(
        "ix_tenant_subscriptions_ends_at",
        table_name="tenant_subscriptions",
    )
    op.drop_index(
        "ix_tenant_subscriptions_current_plan",
        table_name="tenant_subscriptions",
    )
    op.drop_index(
        "uq_tenant_subscriptions_current",
        table_name="tenant_subscriptions",
    )
    op.drop_table("tenant_subscriptions")
    op.drop_table("subscription_plans")

    op.alter_column(
        "tenants",
        "subscription_plan",
        existing_type=sa.String(length=50),
        existing_nullable=False,
        server_default=sa.text("'Basic'"),
    )
    op.drop_index("ix_tenants_status_created_at", table_name="tenants")
    op.drop_constraint("check_tenants_status", "tenants", type_="check")
    op.drop_column("tenants", "updated_at")
    op.drop_column("tenants", "status")
