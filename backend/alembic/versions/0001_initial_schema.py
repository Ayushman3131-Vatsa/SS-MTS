"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-07-21

Applies the DDL in db/schema.sql verbatim (embedded here so this migration
stays reproducible even if db/schema.sql is edited later).
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

UPGRADE_SQL = """
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

CREATE TABLE platform_admins (
    admin_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(255) NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE tenants (
    tenant_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    org_name VARCHAR(255) NOT NULL,
    subscription_plan VARCHAR(50) DEFAULT 'Basic',
    created_by_admin_id UUID NOT NULL REFERENCES platform_admins(admin_id),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE users (
    tenant_id UUID NOT NULL REFERENCES tenants(tenant_id) ON DELETE CASCADE,
    user_id UUID DEFAULT uuid_generate_v4(),
    name VARCHAR(255) NOT NULL,
    email VARCHAR(255) NOT NULL,
    password_hash TEXT NOT NULL,
    role VARCHAR(50) NOT NULL,
    created_by_user_id UUID,
    status VARCHAR(20) DEFAULT 'Active',
    version INT DEFAULT 1,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (tenant_id, user_id),
    UNIQUE (tenant_id, email),
    CONSTRAINT fk_created_by FOREIGN KEY (tenant_id, created_by_user_id) REFERENCES users (tenant_id, user_id),
    CONSTRAINT check_user_role CHECK (role IN ('Tenant Admin', 'Project Manager', 'Employee')),
    CONSTRAINT check_user_status CHECK (status IN ('Active', 'Inactive'))
);

CREATE TABLE projects (
    tenant_id UUID NOT NULL REFERENCES tenants(tenant_id) ON DELETE CASCADE,
    project_id UUID DEFAULT uuid_generate_v4(),
    name VARCHAR(255) NOT NULL,
    client_name VARCHAR(255),
    description TEXT,
    start_date DATE,
    expected_end_date DATE,
    status VARCHAR(50),
    priority VARCHAR(50),
    pm_id UUID,
    dm_id UUID,
    remarks TEXT,
    version INT DEFAULT 1,
    PRIMARY KEY (tenant_id, project_id),
    CONSTRAINT fk_project_pm FOREIGN KEY (tenant_id, pm_id) REFERENCES users (tenant_id, user_id),
    CONSTRAINT fk_project_dm FOREIGN KEY (tenant_id, dm_id) REFERENCES users (tenant_id, user_id),
    CONSTRAINT check_project_status CHECK (status IN ('Not Started', 'In Progress', 'Completed', 'On Hold', 'Cancelled'))
);

CREATE TABLE tasks (
    tenant_id UUID NOT NULL REFERENCES tenants(tenant_id) ON DELETE CASCADE,
    task_id UUID DEFAULT uuid_generate_v4(),
    project_id UUID NOT NULL,
    parent_task_id UUID,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    task_category VARCHAR(100),
    assignee_id UUID,
    technical_lead_id UUID,
    functional_lead_id UUID,
    start_date DATE,
    end_date DATE,
    estimated_hours DECIMAL(10,2) NOT NULL,
    priority VARCHAR(50),
    status VARCHAR(50),
    blocked_by_id UUID,
    remarks TEXT,
    attachment_url TEXT,
    version INT DEFAULT 1,
    PRIMARY KEY (tenant_id, task_id),
    FOREIGN KEY (tenant_id, project_id) REFERENCES projects(tenant_id, project_id),
    CONSTRAINT fk_parent_task FOREIGN KEY (tenant_id, parent_task_id) REFERENCES tasks (tenant_id, task_id),
    CONSTRAINT fk_task_assignee FOREIGN KEY (tenant_id, assignee_id) REFERENCES users (tenant_id, user_id),
    CONSTRAINT fk_task_tech_lead FOREIGN KEY (tenant_id, technical_lead_id) REFERENCES users (tenant_id, user_id),
    CONSTRAINT fk_task_func_lead FOREIGN KEY (tenant_id, functional_lead_id) REFERENCES users (tenant_id, user_id),
    CONSTRAINT check_task_status CHECK (status IN ('New', 'Assigned', 'In Progress', 'Blocked', 'On Hold', 'Under Review', 'Completed', 'Cancelled'))
);

CREATE TABLE task_comments (
    tenant_id UUID NOT NULL REFERENCES tenants(tenant_id) ON DELETE CASCADE,
    comment_id UUID DEFAULT uuid_generate_v4(),
    task_id UUID NOT NULL,
    commented_by_user_id UUID NOT NULL,
    comment_text TEXT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (tenant_id, comment_id),
    FOREIGN KEY (tenant_id, task_id) REFERENCES tasks(tenant_id, task_id),
    CONSTRAINT fk_comment_author FOREIGN KEY (tenant_id, commented_by_user_id) REFERENCES users (tenant_id, user_id)
);

CREATE TABLE daily_progress_logs (
    tenant_id UUID NOT NULL REFERENCES tenants(tenant_id) ON DELETE CASCADE,
    log_id UUID DEFAULT uuid_generate_v4(),
    task_id UUID NOT NULL,
    updated_by_user_id UUID NOT NULL,
    hours_worked DECIMAL(5,2) NOT NULL,
    progress_notes TEXT,
    attachment_url TEXT,
    log_date TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (tenant_id, log_id),
    FOREIGN KEY (tenant_id, task_id) REFERENCES tasks(tenant_id, task_id),
    CONSTRAINT fk_log_author FOREIGN KEY (tenant_id, updated_by_user_id) REFERENCES users (tenant_id, user_id)
);

CREATE TABLE audit_logs (
    tenant_id UUID NOT NULL REFERENCES tenants(tenant_id) ON DELETE CASCADE,
    log_id UUID DEFAULT uuid_generate_v4(),
    entity_type VARCHAR(50),
    entity_id UUID,
    action VARCHAR(50),
    changed_by_user_id UUID,
    changed_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    old_value JSONB,
    new_value JSONB,
    PRIMARY KEY (tenant_id, log_id)
);

CREATE INDEX idx_users_role_lookup ON users (tenant_id, role);
CREATE INDEX idx_tasks_project_lookup ON tasks (tenant_id, project_id);
CREATE INDEX idx_tasks_assignee_lookup ON tasks (tenant_id, assignee_id);
CREATE INDEX idx_tasks_status_lookup ON tasks (tenant_id, status);
CREATE INDEX idx_task_comments_task_lookup ON task_comments (tenant_id, task_id);
CREATE INDEX idx_daily_logs_task_lookup ON daily_progress_logs (tenant_id, task_id);
"""

DOWNGRADE_SQL = """
DROP TABLE IF EXISTS audit_logs;
DROP TABLE IF EXISTS daily_progress_logs;
DROP TABLE IF EXISTS task_comments;
DROP TABLE IF EXISTS tasks;
DROP TABLE IF EXISTS projects;
DROP TABLE IF EXISTS users;
DROP TABLE IF EXISTS tenants;
DROP TABLE IF EXISTS platform_admins;
"""


def _execute_statements(sql: str) -> None:
    # asyncpg's prepared-statement protocol rejects multiple commands in a
    # single execute, unlike psycopg2 — so each DDL statement is sent
    # separately rather than as one multi-statement block.
    for statement in sql.split(";"):
        statement = statement.strip()
        if statement:
            op.execute(statement)


def upgrade() -> None:
    _execute_statements(UPGRADE_SQL)


def downgrade() -> None:
    _execute_statements(DOWNGRADE_SQL)
