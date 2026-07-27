"""enforce canonical workspace slug separators

Revision ID: 0003
Revises: 0002
Create Date: 2026-07-23
"""

from typing import Sequence, Union

from alembic import op

revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 0002-generated slugs already use single separators. Explicit slugs may
    # have used repeated hyphens, so canonicalize them deterministically before
    # tightening the check. Collisions are resolved with the tenant UUID.
    op.drop_constraint(
        "check_tenants_workspace_slug",
        "tenants",
        type_="check",
    )
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
                SELECT tenant_id, workspace_slug
                FROM tenants
                ORDER BY tenant_id
            LOOP
                base_slug := regexp_replace(tenant_row.workspace_slug, '-+', '-', 'g');
                base_slug := trim(BOTH '-' FROM base_slug);
                IF length(base_slug) < 3 THEN
                    base_slug := base_slug || '-org';
                END IF;
                base_slug := rtrim(left(base_slug, 63), '-');
                candidate_slug := base_slug;

                IF EXISTS (
                    SELECT 1
                    FROM tenants
                    WHERE workspace_slug = candidate_slug
                      AND tenant_id <> tenant_row.tenant_id
                ) THEN
                    uuid_text := replace(tenant_row.tenant_id::text, '-', '');
                    collision_attempt := 0;
                    LOOP
                        collision_attempt := collision_attempt + 1;
                        suffix_length := least(4 + (collision_attempt * 4), 32);
                        candidate_slug :=
                            left(base_slug, 62 - suffix_length)
                            || '-'
                            || left(uuid_text, suffix_length);
                        EXIT WHEN NOT EXISTS (
                            SELECT 1
                            FROM tenants
                            WHERE workspace_slug = candidate_slug
                              AND tenant_id <> tenant_row.tenant_id
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
    op.create_check_constraint(
        "check_tenants_workspace_slug",
        "tenants",
        "workspace_slug ~ '^[a-z0-9]+(-[a-z0-9]+)*$'",
    )


def downgrade() -> None:
    op.drop_constraint(
        "check_tenants_workspace_slug",
        "tenants",
        type_="check",
    )
    op.create_check_constraint(
        "check_tenants_workspace_slug",
        "tenants",
        "workspace_slug ~ '^[a-z0-9][a-z0-9-]{1,61}[a-z0-9]$'",
    )
