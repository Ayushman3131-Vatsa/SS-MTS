"""deactivate catalog offerings without backend modules

Revision ID: 0031
Revises: 0030
"""

from typing import Sequence, Union

from alembic import op

revision: str = "0031"
down_revision: Union[str, None] = "0030"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Only offerings with live backend routes should stay ACTIVE by default.
# Platform admins can activate others later from the Offerings screen.
IMPLEMENTED_OFFERING_CODES = ("TASK_MANAGEMENT",)


def upgrade() -> None:
    codes = ", ".join(f"'{code}'" for code in IMPLEMENTED_OFFERING_CODES)
    op.execute(
        f"""
        UPDATE offerings
        SET status = 'INACTIVE',
            updated_at = NOW()
        WHERE status = 'ACTIVE'
          AND code NOT IN ({codes})
        """
    )


def downgrade() -> None:
    op.execute(
        """
        UPDATE offerings
        SET status = 'ACTIVE',
            updated_at = NOW()
        WHERE status = 'INACTIVE'
          AND code IN (
              'CORE_HR',
              'TASK_MANAGEMENT',
              'LEARNING_MANAGEMENT',
              'HELP_DESK',
              'RECRUITING',
              'TIME_ATTENDANCE',
              'EMPLOYEE_SELF_SERVICE',
              'ASSET_MANAGEMENT',
              'PAYROLL',
              'LEAVE_MANAGEMENT',
              'MANAGER_SELF_SERVICE',
              'ANALYTICS_REPORTS',
              'PERFORMANCE_MANAGEMENT',
              'EXPENSE_MANAGEMENT'
          )
        """
    )
