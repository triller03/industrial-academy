"""HWID licensing (blueprint: HWID licensing + offline licence tokens).

The desktop app calls GET /licensing/status on connect and stores the signed
offline token it returns. That token binds the user's plan to the hardware ids
already authorised for their account (Device rows, same 3-device contract the
sync layer enforces), so tiered features keep working through the offline
window. POST /register-hwid binds an extra machine up to the device limit.
"""

from __future__ import annotations

import secrets

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.activity import log_activity
from app.config import get_settings
from app.core.licensing import make_offline_license, verify_offline_license
from app.core.security import get_current_user
from app.database import get_db
from app.models import Device, User
from app.plans import plan_label, plan_key, trial_days_left

router = APIRouter(prefix="/licensing", tags=["licensing"])


class RegisterHwidIn(BaseModel):
    hwid: str = Field(min_length=16, max_length=256)
    label: str | None = Field(default=None, max_length=120)
    platform: str | None = Field(default=None, max_length=64)


def _hwids(db: Session, user_id: int) -> list[str]:
    return [
        d.device_fingerprint
        for d in db.query(Device)
        .filter(Device.user_id == user_id, Device.is_authorized.is_(True))
        .all()
    ]


def _signed_payload(db: Session, user: User) -> dict:
    hwids = _hwids(db, user.id)
    token = make_offline_license(user, hwids=hwids)
    key = plan_key(user)
    return {
        "user_id": user.id,
        "plan_key": key,
        "plan_label": plan_label(key),
        "trial_days_left": trial_days_left(user),
        "device_limit": int(get_settings().device_limit_per_user),
        "bound_hwids": hwids,
        "offline_token": token,
    }


@router.get("/status")
def licensing_status(db: Session = Depends(get_db), current: User = Depends(get_current_user)):
    return _signed_payload(db, current)


@router.post("/register-hwid")
def register_hwid(
    body: RegisterHwidIn,
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
):
    """Bind a hardware id to the account (up to the device limit)."""
    existing = (
        db.query(Device)
        .filter(Device.user_id == current.id, Device.device_fingerprint == body.hwid)
        .first()
    )
    if existing and existing.is_authorized:
        return _signed_payload(db, current)

    bound = _hwids(db, current.id)
    if len(bound) >= int(get_settings().device_limit_per_user):
        raise HTTPException(
            status_code=403,
            detail=f"Device limit of {int(get_settings().device_limit_per_user)} reached. Revoke a device to bind a new hardware id.",
        )

    db.add(Device(
        user_id=current.id,
        device_fingerprint=body.hwid,
        device_label=body.label or f"Licensed device {secrets.token_hex(2).upper()}",
        platform=body.platform,
        is_authorized=True,
    ))
    log_activity(db, current.id, "license.bind_hwid", entity="licensing",
                 detail={"hwid_prefix": body.hwid[:12]})
    db.commit()
    return _signed_payload(db, current)


class VerifyTokenIn(BaseModel):
    offline_token: str


@router.post("/verify")
def verify(token: VerifyTokenIn):
    """Desktop startup check: is this offline token genuine and in date?"""
    payload = verify_offline_license(token.offline_token)
    if payload is None:
        raise HTTPException(status_code=401, detail="Offline licence token invalid or expired.")
    return {
        "valid": True,
        "plan_key": payload.get("plan"),
        "plan_label": payload.get("plan_name"),
        "exp": payload.get("exp"),
        "bound_hwids": payload.get("hwids"),
    }