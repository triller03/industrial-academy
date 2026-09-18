from fastapi import Depends, HTTPException, Request
from fastapi import APIRouter
from sqlalchemy.orm import Session

from app.activity import log_activity
from app.core.security import get_current_user
from app.database import get_db
from app.models import User


router = APIRouter(prefix="/integrations", tags=["integrations"])


def _manager(request: Request):
    return request.app.state.integrations


def _require_admin(current: User) -> None:
    if not current.is_admin:
        raise HTTPException(status_code=403, detail="Administrator privileges required")


@router.get("")
def list_integrations(
    request: Request,
    current: User = Depends(get_current_user),
):
    """Status of every connected tool (FACTORY I/O, S7, WinCC/OPC UA)."""
    return _manager(request).json_status()


@router.post("/modbus/start")
def modbus_start(
    request: Request,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _require_admin(current)
    result = _manager(request).modbus_start()
    log_activity(db, current.id, "integration.modbus_start", entity="modbus", detail=result)
    db.commit()
    return result


@router.post("/modbus/stop")
def modbus_stop(
    request: Request,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _require_admin(current)
    result = _manager(request).modbus_stop()
    log_activity(db, current.id, "integration.modbus_stop", entity="modbus", detail=result)
    db.commit()
    return result


@router.post("/s7/probe")
def s7_probe(
    request: Request,
    current: User = Depends(get_current_user),
):
    _require_admin(current)
    manager = _manager(request)
    if manager.s7 is None:
        return {"ok": False, "detail": "S7 link is disabled in settings"}
    return manager.s7.probe()


@router.post("/opcua/probe")
def opcua_probe(
    request: Request,
    current: User = Depends(get_current_user),
):
    _require_admin(current)
    manager = _manager(request)
    if manager.opcua is None:
        return {"ok": False, "detail": "OPC UA link is disabled in settings"}
    return manager.opcua.probe()


@router.post("/snapshot")
def record_snapshot(
    request: Request,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Records the current FACTORY I/O register map into the audit trail."""
    _require_admin(current)
    manager = _manager(request)
    snapshot = manager.modbus.snapshot() if manager.modbus else {"state": "disabled"}
    log_activity(db, current.id, "integration.snapshot", entity="modbus", detail=snapshot)
    db.commit()
    return {"ok": True}