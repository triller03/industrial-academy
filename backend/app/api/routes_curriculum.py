from fastapi import Depends, HTTPException
from fastapi import APIRouter
from sqlalchemy.orm import Session

from app.activity import log_activity
from app.content.curriculum import CURRICULUM_PROJECTS, CURRICULUM_TRACK, install_curriculum
from app.content.mining_track import MINING_PROJECTS, MINING_TRACK, install_mining_track
from app.core.security import get_current_user
from app.database import get_db
from app.models import Project, User
from app.offline import ensure_bundles

router = APIRouter(prefix="/curriculum", tags=["curriculum"])


def _project_summary(p: Project) -> dict:
    return {
        "slug": p.slug,
        "title": p.title,
        "industry": p.industry,
        "difficulty": p.difficulty,
        "hours": p.hours,
        "description": p.description,
    }


@router.get("/tracks")
def curriculum_tracks(current: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Every learning track with its authored projects."""
    return {
        "tracks": [
            {
                "key": "foundations",
                "name": CURRICULUM_TRACK["name"],
                "blurb": CURRICULUM_TRACK.get("blurb", ""),
                "projects": curriculum_project_list(db, CURRICULUM_PROJECTS),
            },
            {
                "key": "mining",
                "name": MINING_TRACK["name"],
                "blurb": MINING_TRACK["blurb"],
                "projects": curriculum_project_list(db, MINING_PROJECTS),
            },
        ]
    }


@router.get("/mining")
def curriculum_mining(current: User = Depends(get_current_user), db: Session = Depends(get_db)):
    slugs = [project["slug"] for project in MINING_PROJECTS]
    rows = db.query(Project).filter(Project.slug.in_(slugs)).all()
    projects = sorted((_project_summary(p) for p in rows), key=lambda p: slugs.index(p["slug"]))
    return {
        "track": MINING_TRACK,
        "projects": projects,
    }


def curriculum_project_list(db: Session, definitions: list[dict]) -> list[dict]:
    slugs = [d["slug"] for d in definitions]
    rows = db.query(Project).filter(Project.slug.in_(slugs)).all()
    projects = [_project_summary(p) for p in rows]
    projects.sort(key=lambda p: slugs.index(p["slug"]))
    return projects


@router.get("")
def curriculum_index(current: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """The learning track and the authored projects that belong to it."""
    slugs = [project["slug"] for project in CURRICULUM_PROJECTS]
    rows = db.query(Project).filter(Project.slug.in_(slugs)).all()
    projects = [_project_summary(p) for p in rows]
    projects.sort(key=lambda p: slugs.index(p["slug"]))
    return {
        "track": CURRICULUM_TRACK,
        "projects": projects,
    }


@router.post("/install")
def install(
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Admin: install any missing curriculum + mining projects and refresh bundles."""
    if not current.is_admin:
        raise HTTPException(status_code=403, detail="Administrator privileges required")
    created = install_curriculum(db)
    created += [slug for slug in install_mining_track(db) if slug not in created]
    written = ensure_bundles(db)
    db.commit()
    log_activity(
        db,
        current.id,
        "curriculum.install",
        entity="curriculum",
        detail={"created": created, "bundles_written": written},
    )
    db.commit()
    total = db.query(Project).count()
    return {"created": created, "bundles_written": written, "total_projects": total}