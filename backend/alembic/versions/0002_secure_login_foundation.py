"""secure multi-tenant login foundation

Revision ID: 0002
Revises: 0001
Create Date: 2026-07-23
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # CITEXT makes the database enforce the same case-insensitive identity
    # semantics as the application. Fail with a clear message rather than
    # silently merging pre-existing accounts that differ only by case/space.
    op.execute("CREATE EXTENSION IF NOT EXISTS citext")
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1
                FROM platform_admins
                GROUP BY lower(btrim(email))
                HAVING count(*) > 1
            ) THEN
                RAISE EXCEPTION
                    'Cannot migrate platform_admins.email: case-insensitive duplicates exist'
                    USING ERRCODE = '23505';
            END IF;

            IF EXISTS (
                SELECT 1
                FROM users
                GROUP BY tenant_id, lower(btrim(email))
                HAVING count(*) > 1
            ) THEN
                RAISE EXCEPTION
                    'Cannot migrate users.email: case-insensitive duplicates exist within a tenant'
                    USING ERRCODE = '23505';
            END IF;
        END
        $$;
        """
    )

    op.drop_constraint("platform_admins_email_key", "platform_admins", type_="unique")
    op.drop_constraint("users_tenant_id_email_key", "users", type_="unique")
    op.execute("UPDATE platform_admins SET email = lower(btrim(email))")
    op.execute("UPDATE users SET email = lower(btrim(email))")
    op.alter_column(
        "platform_admins",
        "email",
        existing_type=sa.String(length=255),
        type_=postgresql.CITEXT(),
        existing_nullable=False,
        postgresql_using="email::citext",
    )
    op.alter_column(
        "users",
        "email",
        existing_type=sa.String(length=255),
        type_=postgresql.CITEXT(),
        existing_nullable=False,
        postgresql_using="email::citext",
    )
    op.create_unique_constraint("uq_platform_admins_email", "platform_admins", ["email"])
    op.create_unique_constraint("uq_users_tenant_email", "users", ["tenant_id", "email"])

    op.add_column("tenants", sa.Column("workspace_slug", sa.String(length=63), nullable=True))
    op.execute(
        """
        DO $$
        DECLARE
            tenant_row RECORD;
            base_slug TEXT;
            candidate_slug TEXT;
            uuid_text TEXT;
            suffix_length INTEGER;
            collision_attempt INTEGER;
        BEGIN
            FOR tenant_row IN
                SELECT tenant_id, org_name
                FROM tenants
                ORDER BY tenant_id
            LOOP
                base_slug := lower(
                    regexp_replace(coalesce(tenant_row.org_name, ''), '[^A-Za-z0-9]+', '-', 'g')
                );
                base_slug := trim(BOTH '-' FROM base_slug);

                IF length(base_slug) = 0 THEN
                    base_slug := 'tenant';
                ELSIF length(base_slug) < 3 THEN
                    base_slug := base_slug || '-org';
                END IF;

                base_slug := rtrim(left(base_slug, 63), '-');
                candidate_slug := base_slug;

                IF EXISTS (
                    SELECT 1 FROM tenants WHERE workspace_slug = candidate_slug
                ) THEN
                    uuid_text := replace(tenant_row.tenant_id::text, '-', '');
                    collision_attempt := 0;
                    LOOP
                        collision_attempt := collision_attempt + 1;
                        suffix_length := least(4 + (collision_attempt * 4), 32);
                        IF collision_attempt <= 7 THEN
                            candidate_slug :=
                                left(base_slug, 62 - suffix_length)
                                || '-'
                                || left(uuid_text, suffix_length);
                        ELSE
                            candidate_slug :=
                                left(base_slug, 45)
                                || '-'
                                || left(
                                    md5(uuid_text || ':' || collision_attempt::text),
                                    17
                                );
                        END IF;
                        EXIT WHEN NOT EXISTS (
                            SELECT 1 FROM tenants WHERE workspace_slug = candidate_slug
                        );
                    END LOOP;
                END IF;

                UPDATE tenants
                SET workspace_slug = candidate_slug
                WHERE tenant_id = tenant_row.tenant_id;
            END LOOP;
        END
        $$;
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
        "workspace_slug ~ '^[a-z0-9][a-z0-9-]{1,61}[a-z0-9]$'",
    )
    op.create_unique_constraint("uq_tenants_workspace_slug", "tenants", ["workspace_slug"])

    op.create_table(
        "browser_sessions",
        sa.Column(
            "session_id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("uuid_generate_v4()"),
            nullable=False,
        ),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("csrf_token_hash", sa.String(length=64), nullable=False),
        sa.Column("principal_type", sa.String(length=32), nullable=False),
        sa.Column("principal_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "last_seen_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "principal_type IN ('platform_admin', 'tenant_user')",
            name="check_browser_sessions_principal_type",
        ),
        sa.CheckConstraint(
            "(principal_type = 'platform_admin' AND tenant_id IS NULL) OR "
            "(principal_type = 'tenant_user' AND tenant_id IS NOT NULL)",
            name="check_browser_sessions_tenant_context",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.tenant_id"],
            name="fk_browser_sessions_tenant_id",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("session_id", name="pk_browser_sessions"),
        sa.UniqueConstraint("token_hash", name="uq_browser_sessions_token_hash"),
    )
    op.create_index(
        "ix_browser_sessions_principal",
        "browser_sessions",
        ["principal_type", "principal_id"],
        unique=False,
    )
    op.create_index(
        "ix_browser_sessions_expires_at",
        "browser_sessions",
        ["expires_at"],
        unique=False,
    )

    op.create_table(
        "auth_rate_limits",
        sa.Column("throttle_key", sa.String(length=64), nullable=False),
        sa.Column("failures", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("window_started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("locked_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.CheckConstraint("failures >= 0", name="check_auth_rate_limits_failures"),
        sa.PrimaryKeyConstraint("throttle_key", name="pk_auth_rate_limits"),
    )
    op.create_index(
        "ix_auth_rate_limits_locked_until",
        "auth_rate_limits",
        ["locked_until"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_auth_rate_limits_locked_until", table_name="auth_rate_limits")
    op.drop_table("auth_rate_limits")
    op.drop_index("ix_browser_sessions_expires_at", table_name="browser_sessions")
    op.drop_index("ix_browser_sessions_principal", table_name="browser_sessions")
    op.drop_table("browser_sessions")

    op.drop_constraint("uq_tenants_workspace_slug", "tenants", type_="unique")
    op.drop_constraint("check_tenants_workspace_slug", "tenants", type_="check")
    op.drop_column("tenants", "workspace_slug")

    op.drop_constraint("uq_users_tenant_email", "users", type_="unique")
    op.drop_constraint("uq_platform_admins_email", "platform_admins", type_="unique")
    op.alter_column(
        "users",
        "email",
        existing_type=postgresql.CITEXT(),
        type_=sa.String(length=255),
        existing_nullable=False,
        postgresql_using="email::text",
    )
    op.alter_column(
        "platform_admins",
        "email",
        existing_type=postgresql.CITEXT(),
        type_=sa.String(length=255),
        existing_nullable=False,
        postgresql_using="email::text",
    )
    op.create_unique_constraint("users_tenant_id_email_key", "users", ["tenant_id", "email"])
    op.create_unique_constraint("platform_admins_email_key", "platform_admins", ["email"])
    # Leave CITEXT installed: extensions are database-scoped and may have
    # gained consumers outside this application after the upgrade.
