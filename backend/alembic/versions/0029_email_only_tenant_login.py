"""email-only tenant login and separate first-admin bootstrap

Revision ID: 0029
Revises: 0028
Create Date: 2026-08-20
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0029"
down_revision: Union[str, None] = "0028"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    connection = op.get_bind()
    workspace_slug_exists = connection.execute(
        sa.text(
            """
            SELECT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'tenants' AND column_name = 'workspace_slug'
            )
            """
        )
    ).scalar()

    if workspace_slug_exists:
        op.execute(
            """
            DO $$
            DECLARE details text;
            BEGIN
                SELECT string_agg(email, ', ' ORDER BY email) INTO details
                FROM (
                    SELECT lower(email::text) AS email
                    FROM user_accounts
                    GROUP BY lower(email::text)
                    HAVING count(*) > 1
                ) duplicates;
                IF details IS NOT NULL THEN
                    RAISE EXCEPTION 'Cannot enable global tenant-user email uniqueness. Duplicate emails: %', details;
                END IF;

                SELECT string_agg(tenant_code, ', ' ORDER BY tenant_code) INTO details
                FROM tenants
                WHERE contact_name IS NULL OR btrim(contact_name) = '' OR contact_email IS NULL;
                IF details IS NOT NULL THEN
                    RAISE EXCEPTION 'Cannot require primary contacts. Fix tenants: %', details;
                END IF;

                SELECT string_agg(email, ', ' ORDER BY email) INTO details
                FROM (
                    SELECT lower(contact_email::text) AS email
                    FROM tenants
                    GROUP BY lower(contact_email::text)
                    HAVING count(*) > 1
                ) duplicates;
                IF details IS NOT NULL THEN
                    RAISE EXCEPTION 'Primary contact emails must be unique. Duplicate emails: %', details;
                END IF;

                SELECT string_agg(
                    t.tenant_code || ':' || lower(t.contact_email::text),
                    ', ' ORDER BY t.tenant_code
                ) INTO details
                FROM tenants t
                JOIN user_accounts u ON u.email = t.contact_email
                WHERE u.tenant_id <> t.tenant_id;
                IF details IS NOT NULL THEN
                    RAISE EXCEPTION 'Primary contact email belongs to another tenant account: %', details;
                END IF;
            END $$;
            """
        )

    op.execute("ALTER TABLE user_accounts DROP CONSTRAINT IF EXISTS uq_tenant_user_email")
    op.execute("DROP INDEX IF EXISTS ix_user_accounts_email")
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_constraint
                WHERE conname = 'uq_user_accounts_email'
            ) THEN
                ALTER TABLE user_accounts
                    ADD CONSTRAINT uq_user_accounts_email UNIQUE (email);
            END IF;
        END
        $$
        """
    )
    op.execute(
        """
        ALTER TABLE user_accounts
            ADD COLUMN IF NOT EXISTS credential_version INTEGER NOT NULL DEFAULT 1
        """
    )

    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'tenants'
                  AND column_name = 'contact_name'
                  AND is_nullable = 'YES'
            ) THEN
                ALTER TABLE tenants ALTER COLUMN contact_name SET NOT NULL;
            END IF;

            IF EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'tenants'
                  AND column_name = 'contact_email'
                  AND is_nullable = 'YES'
            ) THEN
                ALTER TABLE tenants ALTER COLUMN contact_email SET NOT NULL;
            END IF;
        END
        $$
        """
    )
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_constraint
                WHERE conname = 'uq_tenants_contact_email'
            ) THEN
                ALTER TABLE tenants
                    ADD CONSTRAINT uq_tenants_contact_email UNIQUE (contact_email);
            END IF;
        END
        $$
        """
    )

    if workspace_slug_exists:
        op.drop_constraint("uq_tenants_workspace_slug", "tenants", type_="unique")
        op.drop_constraint("check_tenants_workspace_slug", "tenants", type_="check")
        op.drop_column("tenants", "workspace_slug")


def downgrade() -> None:
    op.add_column("tenants", sa.Column("workspace_slug", sa.String(length=63), nullable=True))
    op.execute(
        """
        UPDATE tenants
        SET workspace_slug =
            left(trim(both '-' from lower(regexp_replace(tenant_code, '[^A-Za-z0-9]+', '-', 'g'))), 50)
            || '-' || substr(replace(tenant_id::text, '-', ''), 1, 8)
        """
    )
    op.alter_column(
        "tenants",
        "workspace_slug",
        existing_type=sa.String(length=63),
        nullable=False,
    )
    op.create_check_constraint(
        "check_tenants_workspace_slug",
        "tenants",
        "workspace_slug ~ '^[a-z0-9]+(-[a-z0-9]+)*$'",
    )
    op.create_unique_constraint("uq_tenants_workspace_slug", "tenants", ["workspace_slug"])

    op.drop_constraint("uq_tenants_contact_email", "tenants", type_="unique")
    op.alter_column("tenants", "contact_email", existing_type=postgresql.CITEXT(), nullable=True)
    op.alter_column(
        "tenants",
        "contact_name",
        existing_type=sa.String(length=255),
        nullable=True,
    )

    op.drop_column("user_accounts", "credential_version")
    op.drop_constraint("uq_user_accounts_email", "user_accounts", type_="unique")
    op.create_unique_constraint(
        "uq_tenant_user_email",
        "user_accounts",
        ["tenant_id", "email"],
    )
    op.create_index("ix_user_accounts_email", "user_accounts", ["email"])
