"""add configuration tables and seed default templates

Revision ID: 0009
Revises: 0008
Create Date: 2026-08-04
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0009"
down_revision: Union[str, None] = "0008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── config_categories ────────────────────────────────────────
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
        sa.Column("display_name", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("icon_key", sa.String(length=50), nullable=False, server_default="file-text"),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "status",
            sa.String(length=20),
            nullable=False,
            server_default=sa.text("'ACTIVE'"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["offering_id"],
            ["offerings.offering_id"],
            ondelete="RESTRICT",
        ),
        sa.CheckConstraint(
            "status IN ('ACTIVE', 'INACTIVE')",
            name="check_config_categories_status",
        ),
        sa.CheckConstraint("sort_order >= 0", name="check_config_categories_sort_order"),
        sa.PrimaryKeyConstraint("category_id"),
        sa.UniqueConstraint("code", name="uq_config_categories_code"),
    )

    # ── config_templates ─────────────────────────────────────────
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
        sa.Column(
            "template_type",
            sa.String(length=50),
            nullable=False,
            server_default=sa.text("'EMAIL'"),
        ),
        sa.Column("subject", sa.String(length=500), nullable=True),
        sa.Column("body", sa.Text(), nullable=False, server_default=""),
        sa.Column(
            "placeholders",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "metadata",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
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
        sa.PrimaryKeyConstraint("template_id"),
        sa.UniqueConstraint("category_id", "code", name="uq_config_templates_category_code"),
    )

    # ── tenant_config_overrides ──────────────────────────────────
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
        sa.Column("body", sa.Text(), nullable=True),
        sa.Column("metadata", postgresql.JSONB(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("updated_by_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.tenant_id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["template_id"],
            ["config_templates.template_id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "updated_by_user_id"],
            ["users.tenant_id", "users.user_id"],
            name="fk_override_updated_by",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("override_id"),
        sa.UniqueConstraint("tenant_id", "template_id", name="uq_tenant_config_override"),
    )

    # ── Indexes ──────────────────────────────────────────────────
    op.create_index(
        "ix_config_categories_offering_id",
        "config_categories",
        ["offering_id"],
    )
    op.create_index(
        "ix_config_templates_category_id",
        "config_templates",
        ["category_id"],
    )
    op.create_index(
        "ix_tenant_config_overrides_tenant_id",
        "tenant_config_overrides",
        ["tenant_id"],
    )

    # ── Seed data: categories ────────────────────────────────────
    #
    # We reference the offerings table by code to look up their UUIDs,
    # then insert categories and templates that belong to them.
    op.execute(
        """
        INSERT INTO config_categories (offering_id, code, display_name, description, icon_key, sort_order)
        SELECT offering_id, 'corehr_email_templates', 'Email Templates', 'Email notifications for Core HR workflows', 'mail', 10
        FROM offerings WHERE code = 'CORE_HR'
        UNION ALL
        SELECT offering_id, 'corehr_letter_templates', 'Letter Templates', 'Formal letters and documents for HR processes', 'file-text', 20
        FROM offerings WHERE code = 'CORE_HR'
        UNION ALL
        SELECT offering_id, 'taskmgmt_email_templates', 'Email Templates', 'Email notifications for Task Management', 'mail', 10
        FROM offerings WHERE code = 'TASK_MANAGEMENT'
        UNION ALL
        SELECT offering_id, 'taskmgmt_notification_templates', 'Notification Templates', 'In-app notifications for Task Management', 'bell', 20
        FROM offerings WHERE code = 'TASK_MANAGEMENT';
        """
    )

    # ── Seed data: Core HR Email Templates ───────────────────────
    op.execute(
        """
        INSERT INTO config_templates (category_id, code, display_name, description, template_type, subject, body, placeholders, sort_order)
        SELECT
            c.category_id,
            v.code,
            v.display_name,
            v.description,
            v.template_type,
            v.subject,
            v.body,
            v.placeholders::jsonb,
            v.sort_order
        FROM config_categories c
        CROSS JOIN (VALUES
            (
                'welcome_email',
                'Welcome Email',
                'Sent to a new employee on their first day',
                'EMAIL',
                'Welcome to {{company_name}}, {{employee_name}}!',
                E'Dear {{employee_name}},\\n\\nWelcome to **{{company_name}}**! We are thrilled to have you join us as **{{position}}**.\\n\\nYour start date is **{{start_date}}** and you will be reporting to **{{manager_name}}**.\\n\\nPlease find your onboarding checklist attached.\\n\\nBest regards,\\n{{company_name}} HR Team',
                '[{"key": "employee_name", "label": "Employee Full Name", "sample_value": "John Doe", "required": true}, {"key": "company_name", "label": "Company Name", "sample_value": "Acme Corp", "required": true}, {"key": "position", "label": "Job Position", "sample_value": "Software Engineer", "required": true}, {"key": "start_date", "label": "Start Date", "sample_value": "2026-09-01", "required": true}, {"key": "manager_name", "label": "Manager Name", "sample_value": "Jane Smith", "required": false}]',
                10
            ),
            (
                'leave_approval',
                'Leave Approval Notification',
                'Sent when a leave request is approved',
                'EMAIL',
                'Leave Request Approved — {{leave_type}}',
                E'Dear {{employee_name}},\\n\\nYour **{{leave_type}}** leave request for **{{leave_dates}}** has been **approved** by {{approver_name}}.\\n\\nPlease ensure your responsibilities are covered during your absence.\\n\\nRegards,\\n{{company_name}} HR',
                '[{"key": "employee_name", "label": "Employee Name", "sample_value": "John Doe", "required": true}, {"key": "leave_type", "label": "Leave Type", "sample_value": "Annual Leave", "required": true}, {"key": "leave_dates", "label": "Leave Dates", "sample_value": "Sep 15-19, 2026", "required": true}, {"key": "approver_name", "label": "Approver Name", "sample_value": "Jane Smith", "required": true}, {"key": "company_name", "label": "Company Name", "sample_value": "Acme Corp", "required": true}]',
                20
            ),
            (
                'leave_rejection',
                'Leave Rejection Notification',
                'Sent when a leave request is rejected',
                'EMAIL',
                'Leave Request Declined — {{leave_type}}',
                E'Dear {{employee_name}},\\n\\nYour **{{leave_type}}** leave request for **{{leave_dates}}** has been **declined** by {{approver_name}}.\\n\\n**Reason:** {{rejection_reason}}\\n\\nPlease discuss with your manager if you have questions.\\n\\nRegards,\\n{{company_name}} HR',
                '[{"key": "employee_name", "label": "Employee Name", "sample_value": "John Doe", "required": true}, {"key": "leave_type", "label": "Leave Type", "sample_value": "Sick Leave", "required": true}, {"key": "leave_dates", "label": "Leave Dates", "sample_value": "Sep 20, 2026", "required": true}, {"key": "approver_name", "label": "Approver Name", "sample_value": "Jane Smith", "required": true}, {"key": "rejection_reason", "label": "Rejection Reason", "sample_value": "Insufficient leave balance", "required": false}, {"key": "company_name", "label": "Company Name", "sample_value": "Acme Corp", "required": true}]',
                30
            ),
            (
                'salary_revision',
                'Salary Revision Notification',
                'Sent when an employee receives a salary revision',
                'EMAIL',
                'Salary Revision — Effective {{effective_date}}',
                E'Dear {{employee_name}},\\n\\nWe are pleased to inform you that your compensation has been revised effective **{{effective_date}}**.\\n\\n| Component | Previous | Revised |\\n|-----------|----------|---------|\\n| Base Salary | {{previous_salary}} | {{new_salary}} |\\n\\nThis reflects our appreciation for your contributions.\\n\\nBest regards,\\n{{company_name}} HR',
                '[{"key": "employee_name", "label": "Employee Name", "sample_value": "John Doe", "required": true}, {"key": "effective_date", "label": "Effective Date", "sample_value": "2026-10-01", "required": true}, {"key": "previous_salary", "label": "Previous Salary", "sample_value": "$80,000", "required": true}, {"key": "new_salary", "label": "New Salary", "sample_value": "$90,000", "required": true}, {"key": "company_name", "label": "Company Name", "sample_value": "Acme Corp", "required": true}]',
                40
            )
        ) AS v(code, display_name, description, template_type, subject, body, placeholders, sort_order)
        WHERE c.code = 'corehr_email_templates';
        """
    )

    # ── Seed data: Core HR Letter Templates ──────────────────────
    op.execute(
        """
        INSERT INTO config_templates (category_id, code, display_name, description, template_type, subject, body, placeholders, sort_order)
        SELECT
            c.category_id,
            v.code,
            v.display_name,
            v.description,
            v.template_type,
            v.subject,
            v.body,
            v.placeholders::jsonb,
            v.sort_order
        FROM config_categories c
        CROSS JOIN (VALUES
            (
                'offer_letter',
                'Offer Letter',
                'Formal offer of employment sent to selected candidates',
                'LETTER',
                'Offer of Employment — {{position}}',
                E'**{{company_name}}**\\n{{company_address}}\\n\\nDate: {{letter_date}}\\n\\n---\\n\\nDear {{candidate_name}},\\n\\nWe are delighted to offer you the position of **{{position}}** at **{{company_name}}**.\\n\\n**Start Date:** {{start_date}}\\n**Compensation:** {{salary}} per annum\\n**Department:** {{department}}\\n**Reporting To:** {{manager_name}}\\n\\nPlease confirm your acceptance by {{acceptance_deadline}}.\\n\\nWe look forward to welcoming you to the team!\\n\\nSincerely,\\n{{hr_name}}\\nHuman Resources',
                '[{"key": "candidate_name", "label": "Candidate Name", "sample_value": "John Doe", "required": true}, {"key": "position", "label": "Position", "sample_value": "Software Engineer", "required": true}, {"key": "company_name", "label": "Company Name", "sample_value": "Acme Corp", "required": true}, {"key": "company_address", "label": "Company Address", "sample_value": "123 Tech Park, Bangalore", "required": false}, {"key": "letter_date", "label": "Letter Date", "sample_value": "August 4, 2026", "required": true}, {"key": "start_date", "label": "Start Date", "sample_value": "September 1, 2026", "required": true}, {"key": "salary", "label": "Salary", "sample_value": "$90,000", "required": true}, {"key": "department", "label": "Department", "sample_value": "Engineering", "required": true}, {"key": "manager_name", "label": "Manager Name", "sample_value": "Jane Smith", "required": false}, {"key": "acceptance_deadline", "label": "Acceptance Deadline", "sample_value": "August 15, 2026", "required": true}, {"key": "hr_name", "label": "HR Contact Name", "sample_value": "Sarah HR", "required": false}]',
                10
            ),
            (
                'probation_confirmation',
                'Probation Confirmation Letter',
                'Confirmation letter after successful completion of probation',
                'LETTER',
                'Confirmation of Employment — {{employee_name}}',
                E'**{{company_name}}**\\n\\nDate: {{letter_date}}\\n\\n---\\n\\nDear {{employee_name}},\\n\\nWe are pleased to confirm your employment with **{{company_name}}** as **{{position}}** effective **{{confirmation_date}}**.\\n\\nYour probation period has been successfully completed. We appreciate your dedication and look forward to your continued contributions.\\n\\nBest regards,\\n{{hr_name}}\\nHuman Resources',
                '[{"key": "employee_name", "label": "Employee Name", "sample_value": "John Doe", "required": true}, {"key": "company_name", "label": "Company Name", "sample_value": "Acme Corp", "required": true}, {"key": "position", "label": "Position", "sample_value": "Software Engineer", "required": true}, {"key": "letter_date", "label": "Letter Date", "sample_value": "November 1, 2026", "required": true}, {"key": "confirmation_date", "label": "Confirmation Date", "sample_value": "November 1, 2026", "required": true}, {"key": "hr_name", "label": "HR Contact Name", "sample_value": "Sarah HR", "required": false}]',
                20
            ),
            (
                'exit_clearance',
                'Exit Clearance Form',
                'Documentation for employee exit and clearance process',
                'LETTER',
                'Exit Clearance — {{employee_name}}',
                E'**{{company_name}}**\\n\\nDate: {{letter_date}}\\n\\n---\\n\\n## Exit Clearance Form\\n\\n**Employee:** {{employee_name}}\\n**Employee ID:** {{employee_id}}\\n**Department:** {{department}}\\n**Last Working Day:** {{last_working_day}}\\n\\n### Clearance Checklist\\n\\n- [ ] Company assets returned\\n- [ ] Access cards surrendered\\n- [ ] Knowledge transfer completed\\n- [ ] Exit interview conducted\\n\\n---\\n\\nAuthorized by: {{hr_name}}',
                '[{"key": "employee_name", "label": "Employee Name", "sample_value": "John Doe", "required": true}, {"key": "employee_id", "label": "Employee ID", "sample_value": "EMP-2024-001", "required": true}, {"key": "company_name", "label": "Company Name", "sample_value": "Acme Corp", "required": true}, {"key": "department", "label": "Department", "sample_value": "Engineering", "required": true}, {"key": "letter_date", "label": "Letter Date", "sample_value": "December 15, 2026", "required": true}, {"key": "last_working_day", "label": "Last Working Day", "sample_value": "December 31, 2026", "required": true}, {"key": "hr_name", "label": "HR Contact Name", "sample_value": "Sarah HR", "required": false}]',
                30
            )
        ) AS v(code, display_name, description, template_type, subject, body, placeholders, sort_order)
        WHERE c.code = 'corehr_letter_templates';
        """
    )

    # ── Seed data: Task Management Email Templates ───────────────
    op.execute(
        """
        INSERT INTO config_templates (category_id, code, display_name, description, template_type, subject, body, placeholders, sort_order)
        SELECT
            c.category_id,
            v.code,
            v.display_name,
            v.description,
            v.template_type,
            v.subject,
            v.body,
            v.placeholders::jsonb,
            v.sort_order
        FROM config_categories c
        CROSS JOIN (VALUES
            (
                'task_assigned',
                'Task Assignment Notification',
                'Sent when a task is assigned to a team member',
                'EMAIL',
                'New Task Assigned: {{task_title}}',
                E'Hi {{assignee_name}},\\n\\nYou have been assigned a new task:\\n\\n**Task:** {{task_title}}\\n**Project:** {{project_name}}\\n**Priority:** {{priority}}\\n**Due Date:** {{due_date}}\\n**Assigned By:** {{assigner_name}}\\n\\n{{task_description}}\\n\\nPlease review and update the status accordingly.',
                '[{"key": "assignee_name", "label": "Assignee Name", "sample_value": "John Doe", "required": true}, {"key": "task_title", "label": "Task Title", "sample_value": "Implement Login API", "required": true}, {"key": "project_name", "label": "Project Name", "sample_value": "SmartSkale v2", "required": true}, {"key": "priority", "label": "Priority", "sample_value": "High", "required": false}, {"key": "due_date", "label": "Due Date", "sample_value": "Sep 15, 2026", "required": false}, {"key": "assigner_name", "label": "Assigned By", "sample_value": "Jane Smith", "required": true}, {"key": "task_description", "label": "Task Description", "sample_value": "Build the REST endpoint for user authentication.", "required": false}]',
                10
            ),
            (
                'task_completed',
                'Task Completion Notification',
                'Sent to stakeholders when a task is marked as complete',
                'EMAIL',
                'Task Completed: {{task_title}}',
                E'Hi {{recipient_name}},\\n\\nThe following task has been marked as **completed**:\\n\\n**Task:** {{task_title}}\\n**Project:** {{project_name}}\\n**Completed By:** {{completer_name}}\\n**Completed On:** {{completion_date}}\\n\\nPlease review if any follow-up is needed.',
                '[{"key": "recipient_name", "label": "Recipient Name", "sample_value": "Jane Smith", "required": true}, {"key": "task_title", "label": "Task Title", "sample_value": "Implement Login API", "required": true}, {"key": "project_name", "label": "Project Name", "sample_value": "SmartSkale v2", "required": true}, {"key": "completer_name", "label": "Completed By", "sample_value": "John Doe", "required": true}, {"key": "completion_date", "label": "Completion Date", "sample_value": "Sep 14, 2026", "required": true}]',
                20
            ),
            (
                'task_overdue',
                'Task Overdue Reminder',
                'Sent when a task has passed its deadline',
                'EMAIL',
                'Overdue Task: {{task_title}}',
                E'Hi {{assignee_name}},\\n\\n⚠️ The following task is **overdue**:\\n\\n**Task:** {{task_title}}\\n**Project:** {{project_name}}\\n**Due Date:** {{due_date}}\\n**Days Overdue:** {{days_overdue}}\\n\\nPlease update the status or reach out to your manager if you need assistance.',
                '[{"key": "assignee_name", "label": "Assignee Name", "sample_value": "John Doe", "required": true}, {"key": "task_title", "label": "Task Title", "sample_value": "Implement Login API", "required": true}, {"key": "project_name", "label": "Project Name", "sample_value": "SmartSkale v2", "required": true}, {"key": "due_date", "label": "Due Date", "sample_value": "Sep 15, 2026", "required": true}, {"key": "days_overdue", "label": "Days Overdue", "sample_value": "3", "required": true}]',
                30
            ),
            (
                'daily_digest',
                'Daily Task Digest',
                'Daily summary of pending and upcoming tasks',
                'EMAIL',
                'Your Daily Task Summary — {{digest_date}}',
                E'Hi {{employee_name}},\\n\\nHere is your task summary for **{{digest_date}}**:\\n\\n**Pending Tasks:** {{pending_count}}\\n**Due Today:** {{due_today_count}}\\n**Overdue:** {{overdue_count}}\\n\\nVisit your dashboard to view details and update progress.',
                '[{"key": "employee_name", "label": "Employee Name", "sample_value": "John Doe", "required": true}, {"key": "digest_date", "label": "Digest Date", "sample_value": "Aug 4, 2026", "required": true}, {"key": "pending_count", "label": "Pending Tasks Count", "sample_value": "5", "required": true}, {"key": "due_today_count", "label": "Due Today Count", "sample_value": "2", "required": true}, {"key": "overdue_count", "label": "Overdue Count", "sample_value": "1", "required": true}]',
                40
            )
        ) AS v(code, display_name, description, template_type, subject, body, placeholders, sort_order)
        WHERE c.code = 'taskmgmt_email_templates';
        """
    )

    # ── Seed data: Task Management Notification Templates ────────
    op.execute(
        """
        INSERT INTO config_templates (category_id, code, display_name, description, template_type, subject, body, placeholders, sort_order)
        SELECT
            c.category_id,
            v.code,
            v.display_name,
            v.description,
            v.template_type,
            v.subject,
            v.body,
            v.placeholders::jsonb,
            v.sort_order
        FROM config_categories c
        CROSS JOIN (VALUES
            (
                'comment_mention',
                'Comment Mention Notification',
                'Sent when someone @mentions a user in a task comment',
                'NOTIFICATION',
                NULL,
                E'**{{mentioner_name}}** mentioned you in a comment on **{{task_title}}**:\\n\\n> {{comment_excerpt}}',
                '[{"key": "mentioner_name", "label": "Mentioner Name", "sample_value": "Jane Smith", "required": true}, {"key": "task_title", "label": "Task Title", "sample_value": "Implement Login API", "required": true}, {"key": "comment_excerpt", "label": "Comment Excerpt", "sample_value": "Can you review the auth flow?", "required": true}]',
                10
            ),
            (
                'task_status_change',
                'Task Status Change',
                'Notification when a task status changes',
                'NOTIFICATION',
                NULL,
                E'**{{changer_name}}** updated the status of **{{task_title}}** from **{{old_status}}** to **{{new_status}}**.',
                '[{"key": "changer_name", "label": "Changed By", "sample_value": "Jane Smith", "required": true}, {"key": "task_title", "label": "Task Title", "sample_value": "Implement Login API", "required": true}, {"key": "old_status", "label": "Previous Status", "sample_value": "In Progress", "required": true}, {"key": "new_status", "label": "New Status", "sample_value": "Completed", "required": true}]',
                20
            )
        ) AS v(code, display_name, description, template_type, subject, body, placeholders, sort_order)
        WHERE c.code = 'taskmgmt_notification_templates';
        """
    )


def downgrade() -> None:
    op.drop_index("ix_tenant_config_overrides_tenant_id", table_name="tenant_config_overrides")
    op.drop_index("ix_config_templates_category_id", table_name="config_templates")
    op.drop_index("ix_config_categories_offering_id", table_name="config_categories")
    op.drop_table("tenant_config_overrides")
    op.drop_table("config_templates")
    op.drop_table("config_categories")
