from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.security import get_current_user
from app.database import get_db
from app.models import User
from app.schemas import ProgressOut, SyncChange, SyncRequest, SyncResult
from app.sync import sync_manager

router = APIRouter(prefix="/sync", tags=["sync"])


@router.post("", response_model=SyncResult)
def sync(
    body: SyncRequest,
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
):
    try:
        sync_manager.assert_device_authorized(db, current, body.device_fingerprint)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc))

    result = sync_manager.sync(db, current, [c.model_dump(mode="json") for c in body.changes])

    applied: list[SyncChange] = []
    for item in result["applied"]:
        applied.append(SyncChange(
            entity="progress",
            local_key=f"{item['project_id']}:{item['section_key']}",
            payload={
                "project_id": item["project_id"],
                "section_key": item["section_key"],
                "status": item["status"],
                "score": item["score"],
            },
            status=item["status"],
            score=item["score"],
        ))

    server_state = [ProgressOut.model_validate(p) for p in result["server_state"]]

    return SyncResult(
        applied=applied,
        conflicts=result["conflicts"],
        server_state=server_state,
    )