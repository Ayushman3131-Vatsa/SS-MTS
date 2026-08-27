"""add unique usernames and restore default configuration templates

Revision ID: 0037
Revises: 0036
"""

from __future__ import annotations

import re
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0037"
down_revision: Union[str, None] = "0036"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _username_base(email: str) -> str:
    local = (email or "user").split("@", 1)[0]
    cleaned = re.sub(r"[^A-Za-z0-9._-]", "", local).strip("._-")
    if not cleaned or not cleaned[0].isalpha():
        cleaned = "user" + re.sub(r"[^A-Za-z0-9]", "", cleaned)
    if not cleaned or not cleaned[0].isalpha():
        cleaned = "user"
    if len(cleaned) < 3:
        cleaned = (cleaned + "xxx")[:3]
    return cleaned[:50]


def _allocate(base: str, used: set[str]) -> str:
    candidate = base
    suffix = 2
    while candidate.casefold() in used:
        extra = str(suffix)
        candidate = f"{base[: max(1, 50 - len(extra))]}{extra}"
        suffix += 1
    used.add(candidate.casefold())
    return candidate


def _backfill(connection, table: str, id_column: str) -> None:
    rows = connection.execute(sa.text(f"SELECT {id_column}, email FROM {table}")).fetchall()
    used: set[str] = set()
    for row_id, email in rows:
        username = _allocate(_username_base(str(email)), used)
        connection.execute(
            sa.text(f"UPDATE {table} SET username = :username WHERE {id_column} = :id"),
            {"username": username, "id": row_id},
        )


def upgrade() -> None:
    op.add_column("user_accounts", sa.Column("username", postgresql.CITEXT(), nullable=True))
    op.add_column("platform_admins", sa.Column("username", postgresql.CITEXT(), nullable=True))

    connection = op.get_bind()
    _backfill(connection, "user_accounts", "id")
    _backfill(connection, "platform_admins", "admin_id")

    op.alter_column("user_accounts", "username", nullable=False)
    op.alter_column("platform_admins", "username", nullable=False)
    op.create_unique_constraint("uq_user_accounts_username", "user_accounts", ["username"])
    op.create_unique_constraint("uq_platform_admins_username", "platform_admins", ["username"])

    _seed_configuration_catalog()


def _exec(sql: str) -> None:
    op.execute(sa.text(sql))


def _seed_configuration_catalog() -> None:
    categories = [
        ("corehr_email_templates", "CORE_HR", "Email Templates", "Email notifications for Core HR workflows", "mail", 10, "EMAIL"),
        ("corehr_letter_templates", "CORE_HR", "Letter Templates", "Formal letters and documents for HR processes", "file-text", 20, "LETTER"),
        ("taskmgmt_email_templates", "TASK_MANAGEMENT", "Email Templates", "Email notifications for Task Management", "mail", 10, "EMAIL"),
        ("taskmgmt_notification_templates", "TASK_MANAGEMENT", "Notification Templates", "In-app notifications for Task Management", "bell", 20, "NOTIFICATION"),
    ]
    for code, offering, name, description, icon, sort_order, template_type in categories:
        _exec(
            f"""
            INSERT INTO config_categories (offering_id, code, display_name, description, icon_key, sort_order, template_type)
            SELECT offering_id, '{code}', '{name}', '{description}', '{icon}', {sort_order}, '{template_type}'
            FROM offerings
            WHERE code = '{offering}'
              AND NOT EXISTS (
                SELECT 1 FROM config_categories c
                WHERE c.offering_id = offerings.offering_id
                  AND (c.code = '{code}' OR c.template_type = '{template_type}')
              )
            ON CONFLICT (code) DO NOTHING
            """
        )
        _exec(
            f"""
            UPDATE config_categories SET template_type = '{template_type}', status = 'ACTIVE'
            WHERE code = '{code}'
              AND NOT EXISTS (
                SELECT 1 FROM config_categories other
                WHERE other.offering_id = config_categories.offering_id
                  AND other.template_type = '{template_type}'
                  AND other.category_id <> config_categories.category_id
              )
            """
        )
    op.execute(
        """
        INSERT INTO config_templates (category_id, code, display_name, description, template_type, subject, body, placeholders, sort_order)
        SELECT c.category_id, v.code, v.display_name, v.description, v.template_type, v.subject, v.body, v.placeholders::jsonb, v.sort_order
        FROM (
            SELECT c.category_id
            FROM config_categories c
            JOIN offerings o ON o.offering_id = c.offering_id
            WHERE o.code = 'CORE_HR'
              AND (c.code = 'corehr_email_templates' OR c.template_type = 'EMAIL')
            ORDER BY CASE WHEN c.code = 'corehr_email_templates' THEN 0 ELSE 1 END
            LIMIT 1
        ) c
        CROSS JOIN (VALUES
            ('welcome_email', 'Welcome Email', 'Sent to a new employee on their first day', 'EMAIL',
             'Welcome to {{company_name}}, {{employee_name}}!',
             E'Dear {{employee_name}},\\n\\nWelcome to **{{company_name}}**.',
             '[{"key": "employee_name", "label": "Employee Full Name", "sample_value": "John Doe", "required": true}, {"key": "company_name", "label": "Company Name", "sample_value": "Acme Corp", "required": true}]',
             10),
            ('leave_approval', 'Leave Approval Notification', 'Sent when a leave request is approved', 'EMAIL',
             'Leave Request Approved — {{leave_type}}',
             E'Dear {{employee_name}},\\n\\nYour leave request has been approved.',
             '[{"key": "employee_name", "label": "Employee Name", "sample_value": "John Doe", "required": true}, {"key": "leave_type", "label": "Leave Type", "sample_value": "Annual Leave", "required": true}]',
             20),
            ('leave_rejection', 'Leave Rejection Notification', 'Sent when a leave request is rejected', 'EMAIL',
             'Leave Request Declined — {{leave_type}}',
             E'Dear {{employee_name}},\\n\\nYour leave request has been declined.',
             '[{"key": "employee_name", "label": "Employee Name", "sample_value": "John Doe", "required": true}, {"key": "leave_type", "label": "Leave Type", "sample_value": "Sick Leave", "required": true}]',
             30),
            ('salary_revision', 'Salary Revision Notification', 'Sent when an employee receives a salary revision', 'EMAIL',
             'Salary Revision — Effective {{effective_date}}',
             E'Dear {{employee_name}},\\n\\nYour compensation has been revised.',
             '[{"key": "employee_name", "label": "Employee Name", "sample_value": "John Doe", "required": true}, {"key": "effective_date", "label": "Effective Date", "sample_value": "2026-10-01", "required": true}]',
             40)
        ) AS v(code, display_name, description, template_type, subject, body, placeholders, sort_order)
        ON CONFLICT (code) DO NOTHING;
        """
    )
    op.execute(
        """
        INSERT INTO config_templates (category_id, code, display_name, description, template_type, subject, body, placeholders, sort_order)
        SELECT c.category_id, v.code, v.display_name, v.description, v.template_type, v.subject, v.body, v.placeholders::jsonb, v.sort_order
        FROM (
            SELECT c.category_id
            FROM config_categories c
            JOIN offerings o ON o.offering_id = c.offering_id
            WHERE o.code = 'CORE_HR'
              AND (c.code = 'corehr_letter_templates' OR c.template_type = 'LETTER')
            ORDER BY CASE WHEN c.code = 'corehr_letter_templates' THEN 0 ELSE 1 END
            LIMIT 1
        ) c
        CROSS JOIN (VALUES
            ('offer_letter', 'Offer Letter', 'Formal offer of employment sent to selected candidates', 'LETTER',
             'Offer of Employment — {{position}}',
             E'Dear {{candidate_name}},\\n\\nWe are delighted to offer you the position of **{{position}}**.',
             '[{"key": "candidate_name", "label": "Candidate Name", "sample_value": "John Doe", "required": true}, {"key": "position", "label": "Position", "sample_value": "Software Engineer", "required": true}]',
             10),
            ('probation_confirmation', 'Probation Confirmation Letter', 'Confirmation letter after successful completion of probation', 'LETTER',
             'Confirmation of Employment — {{employee_name}}',
             E'Dear {{employee_name}},\\n\\nYour probation has been successfully completed.',
             '[{"key": "employee_name", "label": "Employee Name", "sample_value": "John Doe", "required": true}]',
             20),
            ('exit_clearance', 'Exit Clearance Form', 'Documentation for employee exit and clearance process', 'LETTER',
             'Exit Clearance — {{employee_name}}',
             E'## Exit Clearance Form\\n\\n**Employee:** {{employee_name}}',
             '[{"key": "employee_name", "label": "Employee Name", "sample_value": "John Doe", "required": true}]',
             30)
        ) AS v(code, display_name, description, template_type, subject, body, placeholders, sort_order)
        ON CONFLICT (code) DO NOTHING;
        """
    )
    op.execute(
        """
        INSERT INTO config_templates (category_id, code, display_name, description, template_type, subject, body, placeholders, sort_order)
        SELECT c.category_id, v.code, v.display_name, v.description, v.template_type, v.subject, v.body, v.placeholders::jsonb, v.sort_order
        FROM (
            SELECT c.category_id
            FROM config_categories c
            JOIN offerings o ON o.offering_id = c.offering_id
            WHERE o.code = 'TASK_MANAGEMENT'
              AND (c.code = 'taskmgmt_email_templates' OR c.template_type = 'EMAIL')
            ORDER BY CASE WHEN c.code = 'taskmgmt_email_templates' THEN 0 ELSE 1 END
            LIMIT 1
        ) c
        CROSS JOIN (VALUES
            ('task_assigned', 'Task Assignment Notification', 'Sent when a task is assigned to a team member', 'EMAIL',
             'New Task Assigned: {{task_title}}',
             E'Hi {{assignee_name}},\\n\\nYou have been assigned **{{task_title}}**.',
             '[{"key": "assignee_name", "label": "Assignee Name", "sample_value": "John Doe", "required": true}, {"key": "task_title", "label": "Task Title", "sample_value": "Implement Login API", "required": true}]',
             10),
            ('task_completed', 'Task Completion Notification', 'Sent to stakeholders when a task is marked as complete', 'EMAIL',
             'Task Completed: {{task_title}}',
             E'Hi {{recipient_name}},\\n\\n**{{task_title}}** has been completed.',
             '[{"key": "recipient_name", "label": "Recipient Name", "sample_value": "Jane Smith", "required": true}, {"key": "task_title", "label": "Task Title", "sample_value": "Implement Login API", "required": true}]',
             20),
            ('task_overdue', 'Task Overdue Reminder', 'Sent when a task has passed its deadline', 'EMAIL',
             'Overdue Task: {{task_title}}',
             E'Hi {{assignee_name}},\\n\\n**{{task_title}}** is overdue.',
             '[{"key": "assignee_name", "label": "Assignee Name", "sample_value": "John Doe", "required": true}, {"key": "task_title", "label": "Task Title", "sample_value": "Implement Login API", "required": true}]',
             30),
            ('daily_digest', 'Daily Task Digest', 'Daily summary of pending and upcoming tasks', 'EMAIL',
             'Your Daily Task Summary — {{digest_date}}',
             E'Hi {{employee_name}},\\n\\nHere is your task summary for **{{digest_date}}**.',
             '[{"key": "employee_name", "label": "Employee Name", "sample_value": "John Doe", "required": true}, {"key": "digest_date", "label": "Digest Date", "sample_value": "Aug 4, 2026", "required": true}]',
             40)
        ) AS v(code, display_name, description, template_type, subject, body, placeholders, sort_order)
        ON CONFLICT (code) DO NOTHING;
        """
    )
    op.execute(
        """
        INSERT INTO config_templates (category_id, code, display_name, description, template_type, subject, body, placeholders, sort_order)
        SELECT c.category_id, v.code, v.display_name, v.description, v.template_type, NULL, v.body, v.placeholders::jsonb, v.sort_order
        FROM (
            SELECT c.category_id
            FROM config_categories c
            JOIN offerings o ON o.offering_id = c.offering_id
            WHERE o.code = 'TASK_MANAGEMENT'
              AND (c.code = 'taskmgmt_notification_templates' OR c.template_type = 'NOTIFICATION')
            ORDER BY CASE WHEN c.code = 'taskmgmt_notification_templates' THEN 0 ELSE 1 END
            LIMIT 1
        ) c
        CROSS JOIN (VALUES
            ('comment_mention', 'Comment Mention Notification', 'Sent when someone @mentions a user in a task comment', 'NOTIFICATION',
             E'**{{mentioner_name}}** mentioned you on **{{task_title}}**.',
             '[{"key": "mentioner_name", "label": "Mentioner Name", "sample_value": "Jane Smith", "required": true}, {"key": "task_title", "label": "Task Title", "sample_value": "Implement Login API", "required": true}]',
             10),
            ('task_status_change', 'Task Status Change', 'Notification when a task status changes', 'NOTIFICATION',
             E'**{{changer_name}}** updated **{{task_title}}**.',
             '[{"key": "changer_name", "label": "Changed By", "sample_value": "Jane Smith", "required": true}, {"key": "task_title", "label": "Task Title", "sample_value": "Implement Login API", "required": true}]',
             20)
        ) AS v(code, display_name, description, template_type, body, placeholders, sort_order)
        ON CONFLICT (code) DO NOTHING;
        """
    )


def downgrade() -> None:
    op.drop_constraint("uq_platform_admins_username", "platform_admins", type_="unique")
    op.drop_constraint("uq_user_accounts_username", "user_accounts", type_="unique")
    op.drop_column("platform_admins", "username")
    op.drop_column("user_accounts", "username")
