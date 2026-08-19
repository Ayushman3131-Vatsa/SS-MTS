import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.common.models.audit_log import AuditLog


async def record_audit(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    entity_type: str,
    entity_id: uuid.UUID,
    action: str,
    changed_by_user_id: uuid.UUID | None,
    changed_by_admin_id: uuid.UUID | None = None,
    old_value: dict | None = None,
    new_value: dict | None = None,
) -> None:
    """Adds an audit_logs row to the current session. Does not commit —
    callers add this inside the same transaction as the mutation it's
    recording, so the audit trail and the change it describes succeed or
    fail together."""
    session.add(
        AuditLog(
            tenant_id=tenant_id,
            entity_type=entity_type,
            entity_id=entity_id,
            action=action,
            changed_by_user_id=changed_by_user_id,
            changed_by_admin_id=changed_by_admin_id,
            old_value=old_value,
            new_value=new_value,
        )
    )
