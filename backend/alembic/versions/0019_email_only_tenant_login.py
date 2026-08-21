"""email-only tenant login and separate first-admin bootstrap

Revision ID: 0019
Revises: 0018
Create Date: 2026-08-20
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0019"
down_revision: Union[str, None] = "0018"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
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

    op.drop_constraint("uq_tenant_user_email", "user_accounts", type_="unique")
    op.drop_index("ix_user_accounts_email", table_name="user_accounts")
    op.create_unique_constraint("uq_user_accounts_email", "user_accounts", ["email"])
    op.add_column(
        "user_accounts",
        sa.Column("credential_version", sa.Integer(), server_default=sa.text("1"), nullable=False),
    )

    op.alter_column(
        "tenants",
        "contact_name",
        existing_type=sa.String(length=255),
        nullable=False,
    )
    op.alter_column("tenants", "contact_email", existing_type=postgresql.CITEXT(), nullable=False)
    op.create_unique_constraint("uq_tenants_contact_email", "tenants", ["contact_email"])

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
