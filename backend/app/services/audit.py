from sqlalchemy.orm import Session

from app.models import AdminUser, AuditLog


def record(
    db: Session,
    admin: AdminUser | None,
    action: str,
    entity_type: str | None = None,
    entity_id: int | None = None,
    details: dict | None = None,
) -> None:
    """Add an audit entry to the current transaction (committed with the change it describes)."""
    db.add(
        AuditLog(
            admin_id=admin.id if admin else None,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            details=details,
        )
    )
