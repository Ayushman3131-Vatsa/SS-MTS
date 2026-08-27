"""Refactor tenant registration identifiers and add contact designation.

Revision ID: 0027
Revises: 0026
Create Date: 2026-08-19
"""

from typing import Sequence, Union

from alembic import op

revision: str = "0027"
down_revision: Union[str, None] = "0026"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'tenants' AND column_name = 'registration_number'
            ) AND NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'tenants' AND column_name = 'tax_registration_number'
            ) THEN
                ALTER TABLE tenants RENAME COLUMN registration_number TO tax_registration_number;
            END IF;

            IF EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'tenants' AND column_name = 'tax_identifier'
            ) AND NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'tenants' AND column_name = 'pan_number'
            ) THEN
                ALTER TABLE tenants RENAME COLUMN tax_identifier TO pan_number;
            END IF;
        END
        $$
        """
    )
    op.execute(
        "ALTER TABLE tenants ADD COLUMN IF NOT EXISTS contact_designation VARCHAR(100)"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE tenants DROP COLUMN IF EXISTS contact_designation")
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'tenants' AND column_name = 'pan_number'
            ) AND NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'tenants' AND column_name = 'tax_identifier'
            ) THEN
                ALTER TABLE tenants RENAME COLUMN pan_number TO tax_identifier;
            END IF;

            IF EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'tenants' AND column_name = 'tax_registration_number'
            ) AND NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'tenants' AND column_name = 'registration_number'
            ) THEN
                ALTER TABLE tenants RENAME COLUMN tax_registration_number TO registration_number;
            END IF;
        END
        $$
        """
    )
