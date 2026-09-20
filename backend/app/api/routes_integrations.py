import io

from fastapi import Depends, HTTPException, Request
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.activity import log_activity
from app.core.security import get_current_user
from app.database import get_db
from app.models import User
from app.plans import can_tia_bridge
from app.tia import import_tags_csv, probe, validate_scl


router = APIRouter(prefix="/integrations", tags=["integrations"])


class SclValidateIn(BaseModel):
    source: str = Field(..., min_length=8, max_length=200_000)
    block_name: str = Field(default="", max_length=120)


class TagImportIn(BaseModel):
    import_name: str = Field(default="tag-import.csv", max_length=120)
    csv: str = Field(..., max_length=500_000)


def _require_tia(current: User) -> None:
    if not can_tia_bridge(current):
        raise HTTPException(
            status_code=403,
            detail="The TIA Openness bridge is a Professional feature. Upgrade to use the SCL validator and tag import.",
        )


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


@router.get("/tia/probe")
def tia_probe(
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Professional+: report whether a live TIA Openness connector is reachable."""
    _require_tia(current)
    result = probe()
    log_activity(db, current.id, "integration.tia_probe", entity="tia", detail=result)
    db.commit()
    return result


@router.post("/tia/validate-scl")
def tia_validate_scl(
    body: SclValidateIn,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Professional+: deterministic SCL pre-compile check before the project hits TIA."""
    _require_tia(current)
    result = validate_scl(body.source)
    result["block_name"] = body.block_name
    log_activity(db, current.id, "integration.tia_validate_scl", entity="tia",
                 detail={"block": body.block_name, "ok": result.get("ok"), "score": result.get("score")})
    db.commit()
    return result


@router.post("/tia/import-tags")
def tia_import_tags(
    body: TagImportIn,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Professional+: validate a TIA-style CSV tag import against IEC 61131-3."""
    _require_tia(current)
    result = import_tags_csv(body.import_name, body.csv)
    log_activity(db, current.id, "integration.tia_import_tags", entity="tia",
                 detail={"name": body.import_name, "ok": result.get("ok"), "rows": result.get("rows")})
    db.commit()
    return result


@router.get("/tia/template.csv")
def tia_tag_template(current: User = Depends(get_current_user)):
    """Professional+: downloadable CSV template matching the tag-import contract."""
    _require_tia(current)
    csv_text = "Tag,DataType,Address,Description\nFT-001,REAL,IW0.2,Influent flow\nZS-110,BOOL,I1.0,Tramp metal detector\n"
    return StreamingResponse(
        io.StringIO(csv_text),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=asapa-tag-import-template.csv"},
    )