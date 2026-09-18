"""Audit-trail helper. Records a row in ``activity_logs`` for a user action."""

from sqlalchemy.orm import Session

from app.models import ActivityLog


def log_activity(
    db: Session,
    user_id: int,
    action: str,
    entity: str | None = None,
    detail: dict | None = None,
) -> ActivityLog:
    row = ActivityLog(user_id=user_id, action=action, entity=entity, detail=detail)
    db.add(row)
    return row