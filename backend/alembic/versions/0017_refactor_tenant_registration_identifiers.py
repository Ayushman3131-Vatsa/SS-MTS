"""Refactor tenant registration identifiers and add contact designation.

Revision ID: 0017
Revises: 0016
Create Date: 2026-08-19
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0017"
down_revision: Union[str, None] = "0016"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        "tenants",
        "registration_number",
        new_column_name="tax_registration_number",
    )
    op.alter_column(
        "tenants",
        "tax_identifier",
        new_column_name="pan_number",
    )
    op.add_column(
        "tenants",
        sa.Column("contact_designation", sa.String(length=100), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("tenants", "contact_designation")
    op.alter_column(
        "tenants",
        "pan_number",
        new_column_name="tax_identifier",
    )
    op.alter_column(
        "tenants",
        "tax_registration_number",
        new_column_name="registration_number",
    )
