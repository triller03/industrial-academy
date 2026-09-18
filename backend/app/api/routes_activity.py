from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.security import get_current_user
from app.database import get_db
from app.models import ActivityLog, User
from app.schemas import ActivityOut

router = APIRouter(prefix="/activity", tags=["activity"])


@router.get("", response_model=list[ActivityOut])
def my_activity(
    limit: int = Query(default=50, ge=1, le=500),
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
):
    """Audit trail for the caller; administrators see the whole trail."""
    query = db.query(ActivityLog)
    if not current.is_admin:
        query = query.filter(ActivityLog.user_id == current.id)
    rows = query.order_by(ActivityLog.created_at.desc(), ActivityLog.id.desc()).limit(limit).all()
    return [ActivityOut.model_validate(r) for r in rows]