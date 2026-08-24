"""repair tenant offering entitlements schema skipped by stamped migrations

Revision ID: 0026
Revises: 0025
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "0026"
down_revision: Union[str, None] = "0025"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _table_names(connection) -> set[str]:
    rows = connection.execute(
        sa.text("SELECT tablename FROM pg_tables WHERE schemaname = 'public'")
    )
    return {row[0] for row in rows}


def _columns(connection, table: str) -> set[str]:
    rows = connection.execute(
        sa.text(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema = 'public' AND table_name = :table
            """
        ),
        {"table": table},
    )
    return {row[0] for row in rows}


def upgrade() -> None:
    connection = op.get_bind()
    tables = _table_names(connection)

    if "tenant_offering_entitlements" not in tables and "tenant_offerings" in tables:
        op.rename_table("tenant_offerings", "tenant_offering_entitlements")
        op.execute("DROP INDEX IF EXISTS ix_tenant_offerings_offering_id")

    cols = _columns(connection, "tenant_offering_entitlements")
    if not cols:
        return

    if "licensed_at" in cols and "created_at" not in cols:
        op.alter_column(
            "tenant_offering_entitlements",
            "licensed_at",
            new_column_name="created_at",
        )
        cols = _columns(connection, "tenant_offering_entitlements")

    connection.execute(
        sa.text(
            """
            ALTER TABLE tenant_offering_entitlements
                ADD COLUMN IF NOT EXISTS entitlement_id UUID,
                ADD COLUMN IF NOT EXISTS status VARCHAR(20) NOT NULL DEFAULT 'ACTIVE',
                ADD COLUMN IF NOT EXISTS starts_at TIMESTAMPTZ,
                ADD COLUMN IF NOT EXISTS ends_at TIMESTAMPTZ,
                ADD COLUMN IF NOT EXISTS suspended_at TIMESTAMPTZ,
                ADD COLUMN IF NOT EXISTS deactivated_at TIMESTAMPTZ,
                ADD COLUMN IF NOT EXISTS reason TEXT,
                ADD COLUMN IF NOT EXISTS version INTEGER NOT NULL DEFAULT 1,
                ADD COLUMN IF NOT EXISTS updated_by_admin_id UUID,
                ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
            """
        )
    )
    connection.execute(
        sa.text(
            """
            UPDATE tenant_offering_entitlements
            SET entitlement_id = COALESCE(entitlement_id, uuid_generate_v4()),
                starts_at = COALESCE(starts_at, created_at, CURRENT_TIMESTAMP)
            """
        )
    )
    connection.execute(
        sa.text("ALTER TABLE tenant_offering_entitlements ALTER COLUMN entitlement_id SET NOT NULL")
    )
    connection.execute(
        sa.text("ALTER TABLE tenant_offering_entitlements ALTER COLUMN starts_at SET NOT NULL")
    )
    connection.execute(
        sa.text(
            """
            DO $$
            DECLARE
                pk_name text;
            BEGIN
                SELECT conname INTO pk_name
                FROM pg_constraint
                WHERE conrelid = 'tenant_offering_entitlements'::regclass
                  AND contype = 'p'
                  AND conname <> 'pk_tenant_offering_entitlements';
                IF pk_name IS NOT NULL THEN
                    EXECUTE format('ALTER TABLE tenant_offering_entitlements DROP CONSTRAINT %I', pk_name);
                END IF;
            END
            $$
            """
        )
    )
    connection.execute(
        sa.text(
            """
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM pg_constraint
                    WHERE conname = 'pk_tenant_offering_entitlements'
                ) THEN
                    ALTER TABLE tenant_offering_entitlements
                        ADD CONSTRAINT pk_tenant_offering_entitlements PRIMARY KEY (entitlement_id);
                END IF;
            END
            $$
            """
        )
    )
    connection.execute(
        sa.text(
            """
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM pg_constraint
                    WHERE conname = 'fk_entitlements_updated_by_admin_id'
                ) THEN
                    ALTER TABLE tenant_offering_entitlements
                        ADD CONSTRAINT fk_entitlements_updated_by_admin_id
                        FOREIGN KEY (updated_by_admin_id)
                        REFERENCES platform_admins(admin_id)
                        ON DELETE SET NULL;
                END IF;
            END
            $$
            """
        )
    )
    connection.execute(
        sa.text(
            """
            ALTER TABLE tenant_offering_entitlements
                DROP CONSTRAINT IF EXISTS check_tenant_offering_entitlements_status
            """
        )
    )
    connection.execute(
        sa.text(
            """
            ALTER TABLE tenant_offering_entitlements
                ADD CONSTRAINT check_tenant_offering_entitlements_status
                CHECK (status IN ('ACTIVE', 'SUSPENDED', 'EXPIRED', 'DEACTIVATED'))
            """
        )
    )
    connection.execute(
        sa.text(
            """
            ALTER TABLE tenant_offering_entitlements
                DROP CONSTRAINT IF EXISTS check_tenant_offering_entitlements_date_order
            """
        )
    )
    connection.execute(
        sa.text(
            """
            ALTER TABLE tenant_offering_entitlements
                ADD CONSTRAINT check_tenant_offering_entitlements_date_order
                CHECK (ends_at IS NULL OR ends_at > starts_at)
            """
        )
    )
    op.execute("DROP INDEX IF EXISTS uq_tenant_offering_entitlements_open")
    op.create_index(
        "uq_tenant_offering_entitlements_open",
        "tenant_offering_entitlements",
        ["tenant_id", "offering_id"],
        unique=True,
        postgresql_where=sa.text("status IN ('ACTIVE', 'SUSPENDED')"),
    )
    op.execute("DROP INDEX IF EXISTS ix_tenant_offering_entitlements_tenant")
    op.create_index(
        "ix_tenant_offering_entitlements_tenant",
        "tenant_offering_entitlements",
        ["tenant_id", "created_at"],
    )
    op.execute("DROP INDEX IF EXISTS ix_tenant_offering_entitlements_expiry")
    op.create_index(
        "ix_tenant_offering_entitlements_expiry",
        "tenant_offering_entitlements",
        ["status", "ends_at"],
    )

    tables = _table_names(connection)
    if "tenant_offering_events" not in tables:
        op.create_table(
            "tenant_offering_events",
            sa.Column(
                "event_id",
                postgresql.UUID(as_uuid=True),
                server_default=sa.text("uuid_generate_v4()"),
                nullable=False,
            ),
            sa.Column("entitlement_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("event_type", sa.String(length=50), nullable=False),
            sa.Column("actor_admin_id", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column(
                "occurred_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("CURRENT_TIMESTAMP"),
                nullable=False,
            ),
            sa.Column("old_value", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
            sa.Column("new_value", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
            sa.Column("idempotency_key", sa.String(length=255), nullable=False),
            sa.ForeignKeyConstraint(
                ["entitlement_id"],
                ["tenant_offering_entitlements.entitlement_id"],
                ondelete="CASCADE",
            ),
            sa.ForeignKeyConstraint(["tenant_id"], ["tenants.tenant_id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(
                ["actor_admin_id"], ["platform_admins.admin_id"], ondelete="SET NULL"
            ),
            sa.PrimaryKeyConstraint("event_id"),
            sa.UniqueConstraint("idempotency_key", name="uq_tenant_offering_events_idempotency_key"),
        )
        op.create_index(
            "ix_tenant_offering_events_entitlement",
            "tenant_offering_events",
            ["entitlement_id", "occurred_at"],
        )


def downgrade() -> None:
    return
