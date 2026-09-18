from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.activity import log_activity
from app.core.security import get_current_user
from app.database import get_db
from app.models import FaultScenario, OfflineContent, Project, ProjectSection, User
from app.offline import build_bundle, ensure_bundles, read_bundle
from app.schemas import OfflineManifestItem
from app.sync import sync_manager

router = APIRouter(tags=["offline"])


def _latest_bundle(db: Session, project_id: int) -> OfflineContent | None:
    return (
        db.query(OfflineContent)
        .filter(OfflineContent.project_id == project_id)
        .order_by(OfflineContent.created_at.desc(), OfflineContent.id.desc())
        .first()
    )


@router.get("/offline/manifest", response_model=list[OfflineManifestItem])
def manifest(db: Session = Depends(get_db), current: User = Depends(get_current_user)):
    rows = (
        db.query(OfflineContent, Project)
        .join(Project, Project.id == OfflineContent.project_id)
        .filter(Project.status == "published")
        .order_by(OfflineContent.project_id, OfflineContent.created_at.desc())
        .all()
    )

    items: list[OfflineManifestItem] = []
    seen: set[int] = set()
    for record, project in rows:
        if project.id in seen:
            continue
        seen.add(project.id)
        section_count = (
            db.query(ProjectSection).filter(ProjectSection.project_id == project.id).count()
        )
        fault_count = (
            db.query(FaultScenario)
            .filter(FaultScenario.project_id == project.id, FaultScenario.is_published.is_(True))
            .count()
        )
        items.append(
            OfflineManifestItem(
                project_id=project.id,
                slug=project.slug,
                title=project.title,
                industry=project.industry,
                difficulty=project.difficulty,
                version=record.version,
                checksum=record.checksum,
                size_bytes=record.size_bytes,
                section_count=section_count,
                fault_count=fault_count,
                generated_at=record.created_at,
            )
        )
    return items


@router.get("/projects/{project_id}/offline-bundle")
def download_bundle(
    project_id: int,
    device_fingerprint: str = Query(..., min_length=16, max_length=256),
    known_version: str | None = Query(None),
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
):
    try:
        sync_manager.assert_device_authorized(db, current, device_fingerprint)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc))

    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    record = _latest_bundle(db, project_id)
    if record is None:
        ensure_bundles(db)
        record = _latest_bundle(db, project_id)
    if record is None:
        raise HTTPException(status_code=404, detail="No offline bundle available for this project")

    if known_version and known_version == record.version:
        return Response(
            status_code=204,
            headers={"X-Bundle-Version": record.version, "ETag": record.checksum},
        )

    bundle = read_bundle(record)
    if bundle is None:
        bundle = build_bundle(db, project)
        bundle["version"] = record.version
        bundle["checksum"] = record.checksum

    return JSONResponse(
        bundle,
        headers={
            "X-Bundle-Version": record.version,
            "X-Bundle-Checksum": record.checksum,
            "ETag": record.checksum,
            "Cache-Control": "no-cache",
        },
    )


@router.post("/offline/rebuild")
def rebuild_bundles(db: Session = Depends(get_db), current: User = Depends(get_current_user)):
    if not current.is_admin:
        raise HTTPException(status_code=403, detail="Administrator privileges required")
    written = ensure_bundles(db)
    log_activity(db, current.id, "offline.rebuild", entity="offline", detail={"written": written})
    db.commit()
    return {"written": written, "package_dir": str(Path("offline_packages"))}
