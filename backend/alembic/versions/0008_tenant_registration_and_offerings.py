"""add tenant registration profile and licensed offerings

Revision ID: 0008
Revises: 0007
Create Date: 2026-07-23
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0008"
down_revision: Union[str, None] = "0007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("tenants", sa.Column("tenant_code", sa.String(length=30), nullable=True))
    op.add_column("tenants", sa.Column("legal_name", sa.String(length=255), nullable=True))
    op.add_column("tenants", sa.Column("industry", sa.String(length=100), nullable=True))
    op.add_column("tenants", sa.Column("company_size", sa.String(length=50), nullable=True))
    op.add_column("tenants", sa.Column("website", sa.String(length=500), nullable=True))
    op.add_column("tenants", sa.Column("registration_number", sa.String(length=100), nullable=True))
    op.add_column("tenants", sa.Column("tax_identifier", sa.String(length=100), nullable=True))
    op.add_column("tenants", sa.Column("address_line_1", sa.String(length=255), nullable=True))
    op.add_column("tenants", sa.Column("address_line_2", sa.String(length=255), nullable=True))
    op.add_column("tenants", sa.Column("city", sa.String(length=100), nullable=True))
    op.add_column("tenants", sa.Column("state_province", sa.String(length=100), nullable=True))
    op.add_column("tenants", sa.Column("country", sa.String(length=100), nullable=True))
    op.add_column("tenants", sa.Column("postal_code", sa.String(length=30), nullable=True))
    op.add_column("tenants", sa.Column("contact_name", sa.String(length=255), nullable=True))
    op.add_column("tenants", sa.Column("contact_email", postgresql.CITEXT(), nullable=True))
    op.add_column("tenants", sa.Column("contact_phone", sa.String(length=40), nullable=True))

    op.execute(
        """
        UPDATE tenants
        SET tenant_code = 'TENANT_' || upper(substr(replace(tenant_id::text, '-', ''), 1, 8))
        WHERE tenant_code IS NULL
        """
    )
    op.alter_column("tenants", "tenant_code", existing_type=sa.String(length=30), nullable=False)
    op.create_unique_constraint("uq_tenants_tenant_code", "tenants", ["tenant_code"])
    op.create_check_constraint(
        "check_tenants_tenant_code",
        "tenants",
        "tenant_code ~ '^[A-Z0-9][A-Z0-9_-]*$'",
    )

    op.create_table(
        "offerings",
        sa.Column(
            "offering_id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("uuid_generate_v4()"),
            nullable=False,
        ),
        sa.Column("code", sa.String(length=50), nullable=False),
        sa.Column("display_name", sa.String(length=100), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("icon_key", sa.String(length=50), nullable=False),
        sa.Column("route_slug", sa.String(length=63), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=20), server_default=sa.text("'ACTIVE'"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("sort_order >= 0", name="check_offerings_sort_order"),
        sa.CheckConstraint("status IN ('ACTIVE', 'INACTIVE')", name="check_offerings_status"),
        sa.PrimaryKeyConstraint("offering_id"),
        sa.UniqueConstraint("code", name="uq_offerings_code"),
        sa.UniqueConstraint("route_slug", name="uq_offerings_route_slug"),
    )
    op.create_table(
        "tenant_offerings",
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("offering_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("licensed_by_admin_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("licensed_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(
            ["licensed_by_admin_id"],
            ["platform_admins.admin_id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(["offering_id"], ["offerings.offering_id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.tenant_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("tenant_id", "offering_id"),
    )
    op.create_index("ix_tenant_offerings_offering_id", "tenant_offerings", ["offering_id"])

    op.execute(
        """
        INSERT INTO offerings
            (code, display_name, description, icon_key, route_slug, sort_order, status)
        VALUES
            ('CORE_HR', 'Core HR', 'People records and core workforce operations.', 'users', 'core-hr', 10, 'ACTIVE'),
            ('TASK_MANAGEMENT', 'Task Management', 'Projects, assignments, and delivery tracking.', 'clipboard-check', 'task-management', 20, 'ACTIVE'),
            ('LEARNING_MANAGEMENT', 'Learning Management', 'Courses, skills, and employee development.', 'book-open', 'learning-management', 30, 'ACTIVE'),
            ('HELP_DESK', 'Help Desk', 'Internal requests, support queues, and service tracking.', 'headphones', 'help-desk', 40, 'ACTIVE'),
            ('RECRUITING', 'Recruiting', 'Candidates, vacancies, and hiring workflows.', 'user-search', 'recruiting', 50, 'ACTIVE'),
            ('TIME_ATTENDANCE', 'Time & Attendance', 'Attendance, shifts, and work-time visibility.', 'clock', 'time-attendance', 60, 'ACTIVE'),
            ('EMPLOYEE_SELF_SERVICE', 'Employee Self Service', 'Self-service employee profile and requests.', 'user-round', 'employee-self-service', 70, 'ACTIVE'),
            ('ASSET_MANAGEMENT', 'Asset Management', 'Company equipment and asset lifecycle tracking.', 'monitor', 'asset-management', 80, 'ACTIVE'),
            ('PAYROLL', 'Payroll', 'Payroll preparation, review, and employee statements.', 'wallet-cards', 'payroll', 90, 'ACTIVE'),
            ('LEAVE_MANAGEMENT', 'Leave Management', 'Leave policies, requests, and approvals.', 'calendar-days', 'leave-management', 100, 'ACTIVE'),
            ('MANAGER_SELF_SERVICE', 'Manager Self Service', 'Team actions and manager approvals.', 'briefcase-business', 'manager-self-service', 110, 'ACTIVE'),
            ('ANALYTICS_REPORTS', 'Analytics & Reports', 'Workforce and operational reporting.', 'chart-no-axes-combined', 'analytics-reports', 120, 'ACTIVE'),
            ('PERFORMANCE_MANAGEMENT', 'Performance Management', 'Goals, reviews, and performance cycles.', 'chart-spline', 'performance-management', 130, 'ACTIVE'),
            ('EXPENSE_MANAGEMENT', 'Expense Management', 'Expense submissions, reviews, and reimbursements.', 'receipt-text', 'expense-management', 140, 'ACTIVE')
        """
    )


def downgrade() -> None:
    op.drop_index("ix_tenant_offerings_offering_id", table_name="tenant_offerings")
    op.drop_table("tenant_offerings")
    op.drop_table("offerings")
    op.drop_constraint("check_tenants_tenant_code", "tenants", type_="check")
    op.drop_constraint("uq_tenants_tenant_code", "tenants", type_="unique")
    for column in (
        "contact_phone",
        "contact_email",
        "contact_name",
        "postal_code",
        "country",
        "state_province",
        "city",
        "address_line_2",
        "address_line_1",
        "tax_identifier",
        "registration_number",
        "website",
        "company_size",
        "industry",
        "legal_name",
        "tenant_code",
    ):
        op.drop_column("tenants", column)
