"""add time-bound tenant offering entitlements

Revision ID: 0010
Revises: 0009_user_accounts_sessions_roles_hrms
Create Date: 2026-08-05
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0010"
down_revision: Union[str, None] = "0009_user_accounts_sessions_roles_hrms"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "tenants",
        sa.Column("version", sa.Integer(), server_default=sa.text("1"), nullable=False),
    )

    op.add_column("audit_logs", sa.Column("changed_by_admin_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.create_foreign_key(
        "fk_audit_logs_changed_by_admin_id",
        "audit_logs",
        "platform_admins",
        ["changed_by_admin_id"],
        ["admin_id"],
        ondelete="SET NULL",
    )

    op.rename_table("tenant_offerings", "tenant_offering_entitlements")
    op.drop_index("ix_tenant_offerings_offering_id", table_name="tenant_offering_entitlements")
    op.drop_constraint(
        "tenant_offerings_pkey", "tenant_offering_entitlements", type_="primary"
    )
    op.alter_column(
        "tenant_offering_entitlements",
        "licensed_at",
        new_column_name="created_at",
    )
    op.add_column(
        "tenant_offering_entitlements",
        sa.Column("entitlement_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "tenant_offering_entitlements",
        sa.Column("status", sa.String(length=20), server_default=sa.text("'ACTIVE'"), nullable=False),
    )
    op.add_column(
        "tenant_offering_entitlements",
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "tenant_offering_entitlements",
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "tenant_offering_entitlements",
        sa.Column("suspended_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "tenant_offering_entitlements",
        sa.Column("deactivated_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "tenant_offering_entitlements",
        sa.Column("reason", sa.Text(), nullable=True),
    )
    op.add_column(
        "tenant_offering_entitlements",
        sa.Column("version", sa.Integer(), server_default=sa.text("1"), nullable=False),
    )
    op.add_column(
        "tenant_offering_entitlements",
        sa.Column("updated_by_admin_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "tenant_offering_entitlements",
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
    )
    op.execute(
        """
        UPDATE tenant_offering_entitlements
        SET entitlement_id = uuid_generate_v4(), starts_at = created_at
        """
    )
    op.alter_column("tenant_offering_entitlements", "entitlement_id", nullable=False)
    op.alter_column("tenant_offering_entitlements", "starts_at", nullable=False)
    op.create_primary_key(
        "pk_tenant_offering_entitlements",
        "tenant_offering_entitlements",
        ["entitlement_id"],
    )
    op.create_foreign_key(
        "fk_entitlements_updated_by_admin_id",
        "tenant_offering_entitlements",
        "platform_admins",
        ["updated_by_admin_id"],
        ["admin_id"],
        ondelete="SET NULL",
    )
    op.create_check_constraint(
        "check_tenant_offering_entitlements_status",
        "tenant_offering_entitlements",
        "status IN ('ACTIVE', 'SUSPENDED', 'EXPIRED', 'DEACTIVATED')",
    )
    op.create_check_constraint(
        "check_tenant_offering_entitlements_date_order",
        "tenant_offering_entitlements",
        "ends_at IS NULL OR ends_at > starts_at",
    )
    op.create_index(
        "uq_tenant_offering_entitlements_open",
        "tenant_offering_entitlements",
        ["tenant_id", "offering_id"],
        unique=True,
        postgresql_where=sa.text("status IN ('ACTIVE', 'SUSPENDED')"),
    )
    op.create_index(
        "ix_tenant_offering_entitlements_tenant",
        "tenant_offering_entitlements",
        ["tenant_id", "created_at"],
    )
    op.create_index(
        "ix_tenant_offering_entitlements_expiry",
        "tenant_offering_entitlements",
        ["status", "ends_at"],
    )

    op.create_table(
        "tenant_offering_events",
        sa.Column("event_id", postgresql.UUID(as_uuid=True), server_default=sa.text("uuid_generate_v4()"), nullable=False),
        sa.Column("entitlement_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("event_type", sa.String(length=50), nullable=False),
        sa.Column("actor_admin_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("old_value", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("new_value", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("idempotency_key", sa.String(length=255), nullable=False),
        sa.ForeignKeyConstraint(
            ["entitlement_id"], ["tenant_offering_entitlements.entitlement_id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.tenant_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["actor_admin_id"], ["platform_admins.admin_id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("event_id"),
        sa.UniqueConstraint("idempotency_key", name="uq_tenant_offering_events_idempotency_key"),
    )
    op.create_index(
        "ix_tenant_offering_events_entitlement",
        "tenant_offering_events",
        ["entitlement_id", "occurred_at"],
    )

    op.drop_constraint("check_platform_activity_events_type", "platform_activity_events", type_="check")
    op.create_check_constraint(
        "check_platform_activity_events_type",
        "platform_activity_events",
        "event_type IN ("
        "'TENANT_CREATED', 'PLAN_CHANGED', 'TENANT_SUSPENDED', "
        "'TENANT_REACTIVATED', 'DATABASE_ALLOCATION_READY', 'DATABASE_ALLOCATION_FAILED', "
        "'TENANT_ACTIVATED', 'OFFERING_GRANTED', 'OFFERING_SUSPENDED', 'OFFERING_RESUMED', "
        "'OFFERING_DEACTIVATED', 'OFFERING_EXPIRED')",
    )


def downgrade() -> None:
    op.drop_constraint("check_platform_activity_events_type", "platform_activity_events", type_="check")
    op.create_check_constraint(
        "check_platform_activity_events_type",
        "platform_activity_events",
        "event_type IN ("
        "'TENANT_CREATED', 'PLAN_CHANGED', 'TENANT_SUSPENDED', "
        "'TENANT_REACTIVATED', 'DATABASE_ALLOCATION_READY', 'DATABASE_ALLOCATION_FAILED')",
    )
    op.drop_index("ix_tenant_offering_events_entitlement", table_name="tenant_offering_events")
    op.drop_table("tenant_offering_events")
    op.drop_index("ix_tenant_offering_entitlements_expiry", table_name="tenant_offering_entitlements")
    op.drop_index("ix_tenant_offering_entitlements_tenant", table_name="tenant_offering_entitlements")
    op.drop_index("uq_tenant_offering_entitlements_open", table_name="tenant_offering_entitlements")
    op.drop_constraint("check_tenant_offering_entitlements_date_order", "tenant_offering_entitlements", type_="check")
    op.drop_constraint("check_tenant_offering_entitlements_status", "tenant_offering_entitlements", type_="check")
    op.drop_constraint("fk_entitlements_updated_by_admin_id", "tenant_offering_entitlements", type_="foreignkey")
    op.drop_constraint("pk_tenant_offering_entitlements", "tenant_offering_entitlements", type_="primary")
    op.drop_column("tenant_offering_entitlements", "updated_at")
    op.drop_column("tenant_offering_entitlements", "updated_by_admin_id")
    op.drop_column("tenant_offering_entitlements", "version")
    op.drop_column("tenant_offering_entitlements", "reason")
    op.drop_column("tenant_offering_entitlements", "deactivated_at")
    op.drop_column("tenant_offering_entitlements", "suspended_at")
    op.drop_column("tenant_offering_entitlements", "ends_at")
    op.drop_column("tenant_offering_entitlements", "starts_at")
    op.drop_column("tenant_offering_entitlements", "status")
    op.drop_column("tenant_offering_entitlements", "entitlement_id")
    op.alter_column("tenant_offering_entitlements", "created_at", new_column_name="licensed_at")
    op.create_primary_key(
        "tenant_offerings_pkey",
        "tenant_offering_entitlements",
        ["tenant_id", "offering_id"],
    )
    op.create_index("ix_tenant_offerings_offering_id", "tenant_offering_entitlements", ["offering_id"])
    op.rename_table("tenant_offering_entitlements", "tenant_offerings")
    op.drop_constraint("fk_audit_logs_changed_by_admin_id", "audit_logs", type_="foreignkey")
    op.drop_column("audit_logs", "changed_by_admin_id")
    op.drop_column("tenants", "version")
