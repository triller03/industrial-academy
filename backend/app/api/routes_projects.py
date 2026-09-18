from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.content import INDUSTRY_TEMPLATES
from app.content.service import persist_generated_project
from app.core.security import get_current_user
from app.database import get_db
from app.models import FaultScenario, Project, ProjectSection, User, UserProgress
from app.offline import ensure_bundles
from app.schemas import (
    FaultDetailOut,
    FaultScenarioListItem,
    GenerateProjectIn,
    ProjectListItem,
    ProjectOut,
    ProjectProgressOut,
    ProgressOut,
    ProjectSectionOut,
)

router = APIRouter(prefix="/projects", tags=["projects"])


@router.post("/generate", status_code=201, response_model=ProjectListItem)
def generate_project(
    body: GenerateProjectIn,
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
):
    if not current.is_admin:
        raise HTTPException(status_code=403, detail="Administrator privileges required")
    if body.industry not in INDUSTRY_TEMPLATES:
        raise HTTPException(
            status_code=422,
            detail=f"Unknown industry '{body.industry}'. Choose from: {', '.join(sorted(INDUSTRY_TEMPLATES))}",
        )
    project = persist_generated_project(
        db,
        industry=body.industry,
        title=body.title,
        difficulty=body.difficulty,
        description=body.description,
        actor_user_id=current.id,
    )
    ensure_bundles(db)
    return ProjectListItem(
        id=project.id,
        slug=project.slug,
        title=project.title,
        industry=project.industry,
        difficulty=project.difficulty,
        hours=project.hours,
        description=project.description,
    )


@router.get("", response_model=list[ProjectListItem])
def list_projects(db: Session = Depends(get_db)):
    projects = db.query(Project).filter(Project.status == "published").all()
    return [
        ProjectListItem(
            id=p.id,
            slug=p.slug,
            title=p.title,
            industry=p.industry,
            difficulty=p.difficulty,
            hours=p.hours,
            description=p.description,
        )
        for p in projects
    ]


@router.get("/{project_id}", response_model=ProjectOut)
def get_project(project_id: int, db: Session = Depends(get_db)):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


@router.get("/{project_id}/sections/{section_key}", response_model=ProjectSectionOut)
def get_section(project_id: int, section_key: str, db: Session = Depends(get_db)):
    section = (
        db.query(ProjectSection)
        .filter(ProjectSection.project_id == project_id, ProjectSection.key == section_key)
        .first()
    )
    if not section:
        raise HTTPException(status_code=404, detail="Section not found")
    return section


@router.get("/{project_id}/faults", response_model=list[FaultScenarioListItem])
def list_faults(project_id: int, db: Session = Depends(get_db)):
    faults = (
        db.query(FaultScenario)
        .filter(FaultScenario.project_id == project_id, FaultScenario.is_published.is_(True))
        .all()
    )
    return [FaultScenarioListItem.model_validate(f) for f in faults]


@router.get("/{project_id}/faults/{fault_id}", response_model=FaultDetailOut)
def get_fault(project_id: int, fault_id: int, db: Session = Depends(get_db)):
    fault = (
        db.query(FaultScenario)
        .filter(FaultScenario.id == fault_id, FaultScenario.project_id == project_id)
        .first()
    )
    if not fault:
        raise HTTPException(status_code=404, detail="Fault scenario not found")
    # deliberately does NOT expose expected_checks / correct_diagnosis before grading
    return FaultDetailOut(
        id=fault.id,
        slug=fault.slug,
        title=fault.title,
        description=fault.description,
        symptom=fault.symptom,
        operation_notes=fault.operation_notes,
        available_checks=fault.available_checks or fault.expected_checks,
        difficulty=fault.difficulty,
    )


@router.get("/{project_id}/progress", response_model=ProjectProgressOut)
def project_progress(
    project_id: int,
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    rows = db.query(ProjectSection).filter(ProjectSection.project_id == project_id).all()
    sections: list[ProgressOut] = []
    for s in rows:
        progress = (
            db.query(UserProgress)
            .filter(
                UserProgress.user_id == current.id,
                UserProgress.project_id == project_id,
                UserProgress.section_key == s.key,
            )
            .first()
        )
        if progress is None:
            sections.append(
                ProgressOut(
                    user_id=current.id,
                    project_id=project_id,
                    section_key=s.key,
                    status="not_started",
                    score=0.0,
                    attempts=0,
                    time_spent_seconds=0,
                )
            )
            continue
        sections.append(ProgressOut.model_validate(progress))

    completed = sum(1 for s in sections if s.status == "completed")
    total = len(sections)
    return ProjectProgressOut(
        project_id=project_id,
        total_sections=total,
        completed_sections=completed,
        percent=(completed / total * 100) if total else 0.0,
        sections=sections,
    )