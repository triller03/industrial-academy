from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.security import get_current_user
from app.database import get_db
from app.models import Device, User
from app.schemas import DeviceAuthorizeIn, DeviceOut, DeviceRevokeIn
from app.sync import sync_manager

router = APIRouter(prefix="/devices", tags=["devices"])


@router.post("/authorize", response_model=DeviceOut)
def authorize_device(
    body: DeviceAuthorizeIn,
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
):
    try:
        device = sync_manager.authorize_device(
            db, current, body.device_fingerprint, body.device_label, body.platform
        )
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc))
    return DeviceOut.model_validate(device)


@router.get("", response_model=list[DeviceOut])
def list_devices(db: Session = Depends(get_db), current: User = Depends(get_current_user)):
    devices = db.query(Device).filter(Device.user_id == current.id).all()
    return [DeviceOut.model_validate(d) for d in devices]


@router.post("/revoke", response_model=dict)
def revoke_device(
    body: DeviceRevokeIn,
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
):
    ok = sync_manager.revoke_device(db, current, body.device_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Device not found")
    return {"revoked": body.device_id}


@router.post("/{device_id}/touch", response_model=dict)
def touch_device(device_id: int, db: Session = Depends(get_db), current: User = Depends(get_current_user)):
    device = db.query(Device).filter(Device.id == device_id, Device.user_id == current.id).first()
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    device.last_seen = datetime.now(timezone.utc)
    db.commit()
    return {"ok": True}