"""Seed User Access Management and Administration email templates.

Revision ID: 0048
Revises: 0047
"""

import json
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0048"
down_revision: Union[str, None] = "0047"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

OFFERINGS_TO_ENSURE = [
    ("PLATFORM_ADMINISTRATION", "Platform Administration", "Platform infrastructure and tenant lifecycle administration.", "shield-check", "platform-administration", 1),
    ("PLATFORM_USER_ACCESS_MANAGEMENT", "Platform User Access Management", "Platform administrator identity, roles, and console permissions.", "key-round", "platform-user-access", 2),
    ("TENANT_ADMINISTRATION", "Tenant Administration", "Organization workspace settings, overview, and configurations.", "sliders-horizontal", "tenant-administration", 3),
    ("USER_ACCESS_MANAGEMENT", "User Access Management", "Tenant user provisioning, workspace roles, and page access control.", "users", "user-access-management", 4),
]

CATEGORIES_TO_ENSURE = [
    ("PLATFORM_ADMINISTRATION", "platform_admin_emails", "Platform Administration Emails", "EMAIL"),
    ("PLATFORM_USER_ACCESS_MANAGEMENT", "platform_user_access_emails", "Platform User Access Emails", "EMAIL"),
    ("USER_ACCESS_MANAGEMENT", "tenant_user_access_emails", "User Access Emails", "EMAIL"),
    ("TENANT_ADMINISTRATION", "tenant_admin_emails", "Tenant Administration Emails", "EMAIL"),
]

TEMPLATES = [
    # ── PLATFORM_ADMINISTRATION ──────────────────────────────────────────
    (
        "platform_admin_emails",
        "tenant_onboarding_welcome",
        "Tenant Workspace Welcome",
        "Sent to the primary administrator when an organization workspace is registered",
        "EMAIL",
        "Welcome to SmartSkale HRMS — Workspace {{org_name}} is Ready",
        (
            "Dear {{name}},\n\n"
            "Welcome to SmartSkale HRMS! Your organization workspace for **{{org_name}}** has been successfully provisioned.\n\n"
            "**Workspace Details:**\n"
            "- **Organization Name:** {{org_name}}\n"
            "- **Workspace Code:** `{{tenant_code}}`\n"
            "- **Primary Admin Username:** {{username}}\n"
            "- **Temporary Password:** `{{temporary_password}}`\n"
            "- **Workspace Portal:** {{login_url}}\n\n"
            "Please sign in using your temporary credentials and set your permanent password to begin configuring your workspace.\n\n"
            "Best regards,\n"
            "SmartSkale Onboarding Team"
        ),
        [
            {"key": "name", "label": "Admin Name", "sample_value": "Jane Doe", "required": True},
            {"key": "org_name", "label": "Organization Name", "sample_value": "Acme Corp", "required": True},
            {"key": "tenant_code", "label": "Tenant Code", "sample_value": "ACME", "required": True},
            {"key": "username", "label": "Username", "sample_value": "admin_acme", "required": True},
            {"key": "temporary_password", "label": "Temporary Password", "sample_value": "Tr#8kL9!wQ", "required": True},
            {"key": "login_url", "label": "Login URL", "sample_value": "https://hrms.smartskale.com/t/ACME/login", "required": True},
        ],
        10,
    ),
    # ── PLATFORM_USER_ACCESS_MANAGEMENT ──────────────────────────────────
    (
        "platform_user_access_emails",
        "platform_admin_welcome",
        "Platform Admin Welcome (With Roles)",
        "Sent to a new platform administrator when created with assigned roles",
        "EMAIL",
        "[SmartSkale Platform] Welcome to Platform Console — Your Credentials",
        (
            "Dear {{name}},\n\n"
            "You have been granted administrator access to the **SmartSkale Platform Console** with role(s): **{{assigned_roles}}**.\n\n"
            "**Your Credentials:**\n"
            "- **Username / Email:** {{username}}\n"
            "- **Temporary Password:** `{{temporary_password}}`\n"
            "- **Assigned Role(s):** {{assigned_roles}}\n"
            "- **Platform Login URL:** {{login_url}}\n\n"
            "Please sign in and establish your permanent password upon your first login.\n\n"
            "Best regards,\n"
            "SmartSkale Platform Security"
        ),
        [
            {"key": "name", "label": "Admin Name", "sample_value": "Priya Sharma", "required": True},
            {"key": "username", "label": "Username / Email", "sample_value": "priya@platform.example", "required": True},
            {"key": "temporary_password", "label": "Temporary Password", "sample_value": "Tr#8kL9!wQ", "required": True},
            {"key": "assigned_roles", "label": "Assigned Roles", "sample_value": "Platform Admin, Operations", "required": True},
            {"key": "login_url", "label": "Login URL", "sample_value": "https://hrms.smartskale.com/platform/login", "required": True},
        ],
        10,
    ),
    (
        "platform_user_access_emails",
        "platform_admin_welcome_unassigned",
        "Platform Admin Welcome (Unassigned)",
        "Sent to a new platform administrator when created without assigned roles",
        "EMAIL",
        "[SmartSkale Platform] Administrator Account Created",
        (
            "Dear {{name}},\n\n"
            "An administrator account has been created for you on the **SmartSkale Platform Console**.\n\n"
            "**Your Credentials:**\n"
            "- **Username / Email:** {{username}}\n"
            "- **Temporary Password:** `{{temporary_password}}`\n"
            "- **Status:** Pending Role Assignment\n"
            "- **Platform Login URL:** {{login_url}}\n\n"
            "Your account is active. You can sign in to set your permanent password while your functional roles are being configured by a lead administrator.\n\n"
            "Best regards,\n"
            "SmartSkale Platform Security"
        ),
        [
            {"key": "name", "label": "Admin Name", "sample_value": "Amit Verma", "required": True},
            {"key": "username", "label": "Username / Email", "sample_value": "amit@platform.example", "required": True},
            {"key": "temporary_password", "label": "Temporary Password", "sample_value": "Tr#8kL9!wQ", "required": True},
            {"key": "login_url", "label": "Login URL", "sample_value": "https://hrms.smartskale.com/platform/login", "required": True},
        ],
        20,
    ),
    (
        "platform_user_access_emails",
        "platform_admin_role_updated",
        "Platform Admin Role Updated",
        "Sent when a platform administrator's roles are updated or assigned",
        "EMAIL",
        "[SmartSkale Platform] Your Administrative Roles Have Been Updated",
        (
            "Dear {{name}},\n\n"
            "Your administrative roles on the **SmartSkale Platform Console** have been updated.\n\n"
            "**Updated Role Assignment:**\n"
            "- **Current Role(s):** {{assigned_roles}}\n"
            "- **Status:** Active Immediately\n"
            "- **Console Portal:** {{login_url}}\n\n"
            "Your updated permissions are available immediately upon sign-in.\n\n"
            "Best regards,\n"
            "SmartSkale Platform Security"
        ),
        [
            {"key": "name", "label": "Admin Name", "sample_value": "Amit Verma", "required": True},
            {"key": "assigned_roles", "label": "Assigned Roles", "sample_value": "Super Admin", "required": True},
            {"key": "login_url", "label": "Login URL", "sample_value": "https://hrms.smartskale.com/platform/login", "required": True},
        ],
        30,
    ),
    (
        "platform_user_access_emails",
        "platform_admin_password_reset",
        "Platform Admin Password Reset",
        "Sent when a platform administrator password is reset",
        "EMAIL",
        "[SmartSkale Platform] Security Alert: Temporary Password Generated",
        (
            "Dear {{name}},\n\n"
            "A temporary password has been generated for your platform administrator account.\n\n"
            "**Login Credentials:**\n"
            "- **Username:** {{username}}\n"
            "- **Temporary Password:** `{{temporary_password}}`\n"
            "- **Login URL:** {{login_url}}\n\n"
            "Please sign in and create a new password immediately. If you did not request this, please contact platform security.\n\n"
            "Best regards,\n"
            "SmartSkale Platform Security"
        ),
        [
            {"key": "name", "label": "Admin Name", "sample_value": "Priya Sharma", "required": True},
            {"key": "username", "label": "Username", "sample_value": "priya@platform.example", "required": True},
            {"key": "temporary_password", "label": "Temporary Password", "sample_value": "Tr#8kL9!wQ", "required": True},
            {"key": "login_url", "label": "Login URL", "sample_value": "https://hrms.smartskale.com/platform/login", "required": True},
        ],
        40,
    ),
    # ── USER_ACCESS_MANAGEMENT (Tenant) ──────────────────────────────────
    (
        "tenant_user_access_emails",
        "tenant_user_welcome",
        "Tenant User Welcome (With Role)",
        "Sent to an employee when created with assigned roles in a tenant workspace",
        "EMAIL",
        "Welcome to {{org_name}} — Set Up Your Workspace Account",
        (
            "Dear {{name}},\n\n"
            "An employee account has been created for you in **{{org_name}}** with role(s): **{{assigned_roles}}**.\n\n"
            "**Your Account Credentials:**\n"
            "- **Workspace:** {{org_name}} (`{{tenant_code}}`)\n"
            "- **Username / Email:** {{username}}\n"
            "- **Temporary Password:** `{{temporary_password}}`\n"
            "- **Assigned Role(s):** {{assigned_roles}}\n"
            "- **Portal URL:** {{login_url}}\n\n"
            "Please sign in and set your permanent password upon your first login.\n\n"
            "Best regards,\n"
            "{{org_name}} Human Resources"
        ),
        [
            {"key": "name", "label": "Employee Name", "sample_value": "Rahul Kumar", "required": True},
            {"key": "org_name", "label": "Organization Name", "sample_value": "Infosys Limited", "required": True},
            {"key": "tenant_code", "label": "Tenant Code", "sample_value": "INFY", "required": True},
            {"key": "username", "label": "Username", "sample_value": "rahul.kumar", "required": True},
            {"key": "temporary_password", "label": "Temporary Password", "sample_value": "Tr#8kL9!wQ", "required": True},
            {"key": "assigned_roles", "label": "Assigned Roles", "sample_value": "Employee, HR Associate", "required": True},
            {"key": "login_url", "label": "Portal URL", "sample_value": "https://hrms.smartskale.com/t/INFY/login", "required": True},
        ],
        10,
    ),
    (
        "tenant_user_access_emails",
        "tenant_user_welcome_unassigned",
        "Tenant User Welcome (Unassigned)",
        "Sent to an employee when created without assigned roles in a tenant workspace",
        "EMAIL",
        "Welcome to {{org_name}} — Account Created",
        (
            "Dear {{name}},\n\n"
            "An account has been created for you in the **{{org_name}}** workspace.\n\n"
            "**Your Account Details:**\n"
            "- **Workspace:** {{org_name}} (`{{tenant_code}}`)\n"
            "- **Username:** {{username}}\n"
            "- **Temporary Password:** `{{temporary_password}}`\n"
            "- **Status:** Pending Role Assignment\n"
            "- **Portal URL:** {{login_url}}\n\n"
            "Your account is active. You can sign in to set your permanent password while your department roles and modules are being configured.\n\n"
            "Best regards,\n"
            "{{org_name}} Administration"
        ),
        [
            {"key": "name", "label": "Employee Name", "sample_value": "Rahul Kumar", "required": True},
            {"key": "org_name", "label": "Organization Name", "sample_value": "Infosys Limited", "required": True},
            {"key": "tenant_code", "label": "Tenant Code", "sample_value": "INFY", "required": True},
            {"key": "username", "label": "Username", "sample_value": "rahul.kumar", "required": True},
            {"key": "temporary_password", "label": "Temporary Password", "sample_value": "Tr#8kL9!wQ", "required": True},
            {"key": "login_url", "label": "Portal URL", "sample_value": "https://hrms.smartskale.com/t/INFY/login", "required": True},
        ],
        20,
    ),
    (
        "tenant_user_access_emails",
        "tenant_user_role_updated",
        "Tenant User Role Updated",
        "Sent when an employee's workspace role or access privileges are modified",
        "EMAIL",
        "[{{org_name}}] Your System Roles Have Been Updated",
        (
            "Dear {{name}},\n\n"
            "Your access permissions for the **{{org_name}}** portal have been updated by an administrator.\n\n"
            "**Updated Role Assignment:**\n"
            "- **Current Role(s):** {{assigned_roles}}\n"
            "- **Organization:** {{org_name}} (`{{tenant_code}}`)\n"
            "- **Portal URL:** {{login_url}}\n\n"
            "Your updated permissions and modules are available immediately upon sign-in.\n\n"
            "Best regards,\n"
            "{{org_name}} Human Resources"
        ),
        [
            {"key": "name", "label": "Employee Name", "sample_value": "Rahul Kumar", "required": True},
            {"key": "org_name", "label": "Organization Name", "sample_value": "Infosys Limited", "required": True},
            {"key": "tenant_code", "label": "Tenant Code", "sample_value": "INFY", "required": True},
            {"key": "assigned_roles", "label": "Assigned Roles", "sample_value": "Project Manager", "required": True},
            {"key": "login_url", "label": "Portal URL", "sample_value": "https://hrms.smartskale.com/t/INFY/login", "required": True},
        ],
        30,
    ),
    (
        "tenant_user_access_emails",
        "tenant_user_password_reset",
        "Tenant User Password Reset",
        "Sent when an employee's temporary password is reset",
        "EMAIL",
        "Security Alert: Temporary Password Generated for {{username}}",
        (
            "Dear {{name}},\n\n"
            "A temporary password has been generated for your account.\n\n"
            "**Temporary Sign-In Details:**\n"
            "- **Workspace:** {{org_name}} (`{{tenant_code}}`)\n"
            "- **Username:** {{username}}\n"
            "- **Temporary Password:** `{{temporary_password}}`\n"
            "- **Portal URL:** {{login_url}}\n\n"
            "Please sign in and set your new password. If you did not request this, please contact your workspace administrator immediately.\n\n"
            "Best regards,\n"
            "{{org_name}} Security & Access"
        ),
        [
            {"key": "name", "label": "Employee Name", "sample_value": "Rahul Kumar", "required": True},
            {"key": "org_name", "label": "Organization Name", "sample_value": "Infosys Limited", "required": True},
            {"key": "tenant_code", "label": "Tenant Code", "sample_value": "INFY", "required": True},
            {"key": "username", "label": "Username", "sample_value": "rahul.kumar", "required": True},
            {"key": "temporary_password", "label": "Temporary Password", "sample_value": "Tr#8kL9!wQ", "required": True},
            {"key": "login_url", "label": "Portal URL", "sample_value": "https://hrms.smartskale.com/t/INFY/login", "required": True},
        ],
        40,
    ),
]


def upgrade() -> None:
    conn = op.get_bind()

    # 1. Ensure offerings exist
    for code, display_name, description, icon_key, route_slug, sort_order in OFFERINGS_TO_ENSURE:
        conn.execute(
            sa.text(
                """
                INSERT INTO offerings (code, display_name, description, icon_key, route_slug, sort_order, status)
                VALUES (:code, :display_name, :description, :icon_key, :route_slug, :sort_order, 'ACTIVE')
                ON CONFLICT (code) DO UPDATE SET
                    display_name = EXCLUDED.display_name,
                    description = EXCLUDED.description,
                    status = 'ACTIVE'
                """
            ),
            {
                "code": code,
                "display_name": display_name,
                "description": description,
                "icon_key": icon_key,
                "route_slug": route_slug,
                "sort_order": sort_order,
            },
        )

    # 2. Ensure config categories exist
    for offering_code, cat_code, cat_name, template_type in CATEGORIES_TO_ENSURE:
        conn.execute(
            sa.text(
                """
                INSERT INTO config_categories (offering_id, code, display_name, template_type, status)
                SELECT offering_id, :cat_code, :cat_name, :template_type, 'ACTIVE'
                FROM offerings WHERE code = :offering_code
                ON CONFLICT (code) DO UPDATE SET
                    display_name = EXCLUDED.display_name,
                    template_type = EXCLUDED.template_type,
                    status = 'ACTIVE'
                """
            ),
            {
                "offering_code": offering_code,
                "cat_code": cat_code,
                "cat_name": cat_name,
                "template_type": template_type,
            },
        )

    # 3. Ensure config templates exist
    for cat_code, code, display_name, description, template_type, subject, body, placeholders, sort_order in TEMPLATES:
        conn.execute(
            sa.text(
                """
                INSERT INTO config_templates (category_id, code, display_name, description, template_type, subject, body, placeholders, sort_order, is_active, version)
                SELECT category_id, :code, :display_name, :description, :template_type, :subject, :body, CAST(:placeholders AS jsonb), :sort_order, true, 1
                FROM config_categories WHERE code = :cat_code
                ON CONFLICT (code) DO UPDATE SET
                    display_name = EXCLUDED.display_name,
                    description = EXCLUDED.description,
                    subject = EXCLUDED.subject,
                    body = EXCLUDED.body,
                    placeholders = EXCLUDED.placeholders,
                    is_active = true
                """
            ),
            {
                "cat_code": cat_code,
                "code": code,
                "display_name": display_name,
                "description": description,
                "template_type": template_type,
                "subject": subject,
                "body": body,
                "placeholders": json.dumps(placeholders),
                "sort_order": sort_order,
            },
        )


def downgrade() -> None:
    conn = op.get_bind()
    template_codes = [t[1] for t in TEMPLATES]
    conn.execute(
        sa.text("DELETE FROM config_templates WHERE code = ANY(:codes)"),
        {"codes": template_codes},
    )
