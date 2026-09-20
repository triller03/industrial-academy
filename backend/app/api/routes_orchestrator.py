from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.activity import log_activity
from app.core.security import get_current_user
from app.database import get_db
from app.models import Project, User
from app.orchestrator import orchestration_engine, launch_tool
from app.plans import can_public_portfolio, can_schematic_viewer, can_tia_bridge

router = APIRouter(prefix="/orchestrator", tags=["orchestrator"])


class OrchestratorAdvanceIn(BaseModel):
    step: int = Field(default=1, ge=1, le=9)


class OrchestratorLaunchIn(BaseModel):
    actions: list[str] = Field(default_factory=list, max_length=12)


GATE_CHECK = {
    "can_tia_bridge": can_tia_bridge,
    "can_schematic_viewer": can_schematic_viewer,
    "can_public_portfolio": can_public_portfolio,
}


def _require_gate(user: User, gate_key: str | None) -> None:
    if not gate_key:
        return
    check = GATE_CHECK.get(gate_key)
    if check and not check(user):
        raise HTTPException(
            status_code=403,
            detail=f"This stage is a paid feature on your plan. Upgrade to drive the {gate_key} workflow.",
        )


def _project(db: Session, project_id: int) -> Project:
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


@router.get("/status")
def orchestrator_status(current: User = Depends(get_current_user)):
    if not current:
        raise HTTPException(status_code=401, detail="Authentication required")
    return orchestration_engine.status()


@router.get("/projects/{project_id}/workflow")
def project_workflow(
    project_id: int,
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
):
    project = _project(db, project_id)
    return {
        "project_id": project.id,
        "title": project.title,
        "pipeline": orchestration_engine.status()["pipeline"],
        **orchestration_engine.run_from_stage(project.orchestration_stage),
    }


@router.post("/projects/{project_id}/advance")
def advance_project(
    project_id: int,
    body: OrchestratorAdvanceIn,
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
):
    project = _project(db, project_id)
    result = orchestration_engine.advance(project.orchestration_stage, step=body.step)
    _require_gate(current, result["stage"].get("gate"))
    project.orchestration_stage = result["stage_index"]
    db.add(project)
    log_activity(db, current.id, "orchestrator.advance", entity=f"project:{project_id}",
                 detail={"stage": result["stage_key"]})
    db.commit()
    return result


@router.post("/projects/{project_id}/regress")
def regress_project(
    project_id: int,
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
):
    project = _project(db, project_id)
    result = orchestration_engine.rollback(project.orchestration_stage)
    project.orchestration_stage = result["stage_index"]
    db.add(project)
    log_activity(db, current.id, "orchestrator.regress", entity=f"project:{project_id}",
                 detail={"stage": result["stage_key"]})
    db.commit()
    return result


@router.post("/tools/{tool_key}/launch")
def launch_tool_route(
    tool_key: str,
    body: OrchestratorLaunchIn,
    current: User = Depends(get_current_user),
):
    """Launch (or simulate) a desktop engineering tool. Admin-only when live."""
    if not current.is_admin:
        raise HTTPException(
            status_code=403,
            detail="Launching engineering tools is an administrative action on this host.",
        )
    if tool_key not in ("tia", "wincc", "factoryio"):
        raise HTTPException(status_code=422, detail=f"Unknown tool '{tool_key}'.")
    return launch_tool(
        orchestration_engine.settings.orchestrator_app_paths,
        orchestration_engine.mode,
        tool_key,
        body.actions,
    )