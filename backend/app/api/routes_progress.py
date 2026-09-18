import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.activity import log_activity
from app.core.security import get_current_user
from app.database import get_db
from app.models import Certificate, PortfolioEntry, Project, ProjectSection, User, UserProgress
from app.schemas import ProgressOut, ProgressUpdateIn

router = APIRouter(prefix="/progress", tags=["progress"])


@router.get("", response_model=list[ProgressOut])
def my_progress(db: Session = Depends(get_db), current: User = Depends(get_current_user)):
    rows = db.query(UserProgress).filter(UserProgress.user_id == current.id).all()
    return [ProgressOut.model_validate(r) for r in rows]


@router.post("", response_model=ProgressOut)
def update_progress(
    body: ProgressUpdateIn,
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
):
    record = (
        db.query(UserProgress)
        .filter(
            UserProgress.user_id == current.id,
            UserProgress.project_id == body.project_id,
            UserProgress.section_key == body.section_key,
        )
        .first()
    )
    if record is None:
        record = UserProgress(
            user_id=current.id,
            project_id=body.project_id,
            section_key=body.section_key,
            status=body.status,
            score=body.score,
            time_spent_seconds=body.time_spent_seconds,
        )
        db.add(record)
    else:
        record.status = body.status
        record.score = max(record.score, body.score)
        record.time_spent_seconds += max(0, body.time_spent_seconds)
        record.attempts += 1
        if body.status == "completed":
            record.completed_at = record.completed_at or datetime.now(timezone.utc)
    db.commit()
    db.refresh(record)

    if body.status == "completed":
        log_activity(
            db,
            current.id,
            "section.completed",
            entity=f"project:{record.project_id}:section:{record.section_key}",
            detail={"score": record.score, "attempts": record.attempts},
        )
        db.commit()
        _finalize_completed(current.id, record, db)
    return record


def _finalize_completed(user_id: int, record: UserProgress, db: Session) -> None:
    total_sections = (
        db.query(ProjectSection).filter(ProjectSection.project_id == record.project_id).count()
    )
    completed = (
        db.query(UserProgress)
        .filter(
            UserProgress.user_id == user_id,
            UserProgress.project_id == record.project_id,
            UserProgress.status == "completed",
        )
        .count()
    )
    if total_sections == 0 or completed < total_sections:
        return

    already_cert = (
        db.query(Certificate)
        .filter(Certificate.user_id == user_id, Certificate.project_id == record.project_id)
        .first()
    )
    if already_cert:
        return

    project = db.query(Project).filter(Project.id == record.project_id).first()
    if not project:
        return

    db.add(Certificate(
        user_id=user_id,
        project_id=record.project_id,
        certificate_ref=f"CERT-{project.slug.upper()}-{uuid.uuid4().hex[:10].upper()}",
        score=100.0,
        verification_token=uuid.uuid4().hex,
    ))
    db.add(PortfolioEntry(
        user_id=user_id,
        project_id=record.project_id,
        entry_ref=f"P-{project.slug.upper()}-{uuid.uuid4().hex[:8].upper()}",
        title=project.title,
        summary=f"Completed {project.title} — full 17-section engineering lifecycle.",
    ))
    log_activity(
        db,
        user_id,
        "credential.issued",
        entity=f"project:{record.project_id}",
        detail={"kind": "certificate+portfolio", "project": project.slug},
    )
    db.commit()