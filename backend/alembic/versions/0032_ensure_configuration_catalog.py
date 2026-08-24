"""ensure configuration catalog tables exist

Revision ID: 0032
Revises: 0031
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0032"
down_revision: Union[str, None] = "0031"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_table(connection, name: str) -> bool:
    return bool(
        connection.execute(
            sa.text(
                "SELECT EXISTS (SELECT 1 FROM pg_tables WHERE schemaname = 'public' AND tablename = :name)"
            ),
            {"name": name},
        ).scalar()
    )


def _has_column(connection, table: str, column: str) -> bool:
    return bool(
        connection.execute(
            sa.text(
                """
                SELECT EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_schema = 'public' AND table_name = :table AND column_name = :column
                )
                """
            ),
            {"table": table, "column": column},
        ).scalar()
    )


def upgrade() -> None:
    connection = op.get_bind()
    if not _has_table(connection, "config_categories"):
        op.create_table(
            "config_categories",
            sa.Column(
                "category_id",
                postgresql.UUID(as_uuid=True),
                server_default=sa.text("gen_random_uuid()"),
                nullable=False,
            ),
            sa.Column("offering_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("code", sa.String(length=100), nullable=False),
            sa.Column(
                "template_type",
                sa.String(length=50),
                nullable=False,
                server_default=sa.text("'OTHER'"),
            ),
            sa.Column("display_name", sa.String(length=200), nullable=False),
            sa.Column("description", sa.Text(), nullable=False, server_default=""),
            sa.Column("icon_key", sa.String(length=50), nullable=False, server_default="file-text"),
            sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("status", sa.String(length=20), nullable=False, server_default=sa.text("'ACTIVE'")),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.ForeignKeyConstraint(["offering_id"], ["offerings.offering_id"], ondelete="RESTRICT"),
            sa.CheckConstraint("status IN ('ACTIVE', 'INACTIVE')", name="check_config_categories_status"),
            sa.CheckConstraint(
                "template_type IN ('EMAIL', 'LETTER', 'NOTIFICATION', 'OTHER')",
                name="check_config_categories_type",
            ),
            sa.CheckConstraint("sort_order >= 0", name="check_config_categories_sort_order"),
            sa.PrimaryKeyConstraint("category_id"),
            sa.UniqueConstraint("code", name="uq_config_categories_code"),
            sa.UniqueConstraint("offering_id", "template_type", name="uq_config_categories_offering_type"),
        )
        op.create_index("ix_config_categories_offering_id", "config_categories", ["offering_id"])
    elif not _has_column(connection, "config_categories", "template_type"):
        op.add_column(
            "config_categories",
            sa.Column("template_type", sa.String(length=50), server_default=sa.text("'OTHER'"), nullable=False),
        )

    if not _has_table(connection, "config_templates"):
        op.create_table(
            "config_templates",
            sa.Column(
                "template_id",
                postgresql.UUID(as_uuid=True),
                server_default=sa.text("gen_random_uuid()"),
                nullable=False,
            ),
            sa.Column("category_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("code", sa.String(length=100), nullable=False),
            sa.Column("display_name", sa.String(length=200), nullable=False),
            sa.Column("description", sa.Text(), nullable=False, server_default=""),
            sa.Column("template_type", sa.String(length=50), nullable=False, server_default=sa.text("'EMAIL'")),
            sa.Column("subject", sa.String(length=500), nullable=True),
            sa.Column("body", sa.Text(), nullable=False, server_default=""),
            sa.Column("placeholders", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
            sa.Column("metadata", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
            sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.ForeignKeyConstraint(
                ["category_id"],
                ["config_categories.category_id"],
                ondelete="CASCADE",
            ),
            sa.CheckConstraint(
                "template_type IN ('EMAIL', 'LETTER', 'NOTIFICATION', 'OTHER')",
                name="check_config_templates_type",
            ),
            sa.CheckConstraint("sort_order >= 0", name="check_config_templates_sort_order"),
            sa.CheckConstraint("version >= 1", name="check_config_templates_version"),
            sa.PrimaryKeyConstraint("template_id"),
            sa.UniqueConstraint("code", name="uq_config_templates_code"),
        )
        op.create_index("ix_config_templates_category_id", "config_templates", ["category_id"])
    elif not _has_column(connection, "config_templates", "version"):
        op.add_column(
            "config_templates",
            sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        )

    if not _has_table(connection, "tenant_config_overrides"):
        op.create_table(
            "tenant_config_overrides",
            sa.Column(
                "override_id",
                postgresql.UUID(as_uuid=True),
                server_default=sa.text("gen_random_uuid()"),
                nullable=False,
            ),
            sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("template_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("subject", sa.String(length=500), nullable=True),
            sa.Column("body", sa.Text(), nullable=False),
            sa.Column("metadata", postgresql.JSONB(), nullable=True),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
            sa.Column("updated_by_user_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.ForeignKeyConstraint(["tenant_id"], ["tenants.tenant_id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(
                ["template_id"],
                ["config_templates.template_id"],
                ondelete="CASCADE",
            ),
            sa.ForeignKeyConstraint(
                ["tenant_id", "updated_by_user_id"],
                ["user_accounts.tenant_id", "user_accounts.id"],
                name="fk_override_updated_by",
                ondelete="RESTRICT",
            ),
            sa.PrimaryKeyConstraint("override_id"),
            sa.UniqueConstraint("tenant_id", "template_id", name="uq_tenant_config_override"),
        )
        op.create_index("ix_tenant_config_overrides_tenant_id", "tenant_config_overrides", ["tenant_id"])


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS tenant_config_overrides")
    op.execute("DROP TABLE IF EXISTS config_templates")
    op.execute("DROP TABLE IF EXISTS config_categories")
