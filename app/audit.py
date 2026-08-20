from sqlalchemy.orm import Session

from app import models


def log_action(
    db: Session,
    user: models.User | None,
    action: models.AuditAction,
    entity_type: str,
    entity_id: int | None,
    description: str = "",
):
    entry = models.AuditLog(
        user_id=user.id if user else None,
        username=user.username if user else "system",
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        description=description,
    )
    db.add(entry)
    db.commit()
