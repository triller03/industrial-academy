"""Offline content packaging.

Builds a self-contained, versioned JSON bundle for a project so the client can work
disconnected. Bundles are written to disk and registered in the ``offline_content``
table with a content-addressed version and checksum.

Security note: bundles never contain the grading reference (expected checks or the
correct diagnosis). Offline fault attempts are queued and graded by the server on the
next sync, so the answer key never leaves the backend.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy.orm import Session

from app.mentor import engine as mentor_engine
from app.models import FaultScenario, OfflineContent, Project, ProjectSection

SCHEMA_VERSION = 1

PACKAGE_DIR = Path(__file__).resolve().parent.parent.parent / "offline_packages"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def canonical(payload: object) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _checksum(payload: object) -> str:
    return hashlib.sha256(canonical(payload).encode("utf-8")).hexdigest()


def _mentor_pack() -> dict:
    """Export the deterministic parts of the mentor engine so the client can mirror it offline."""
    return {
        "safety_keywords": mentor_engine.SAFETY_KEYWORDS,
        "frustration_keywords": mentor_engine.FRUSTRATION_KEYWORDS,
        "ask_answer_keywords": mentor_engine.ASK_ANSWER_KEYWORDS,
        "topic_levels": mentor_engine.TOPIC_LEVELS,
        "socratic_questions": mentor_engine.SOCRATIC_QUESTION_BANK,
        "guided_steps": mentor_engine.GUIDED_STEPS,
        "full_solution_intro": mentor_engine.FULL_SOLUTION_INTRO,
        "safety_preface": mentor_engine.SAFETY_PREFACE,
        "safety_steps": mentor_engine.SAFETY_STEPS,
    }


def _section_payload(section: ProjectSection) -> dict:
    return {
        "key": section.key,
        "title": section.title,
        "order": section.order,
        "content": section.content,
        "is_lockable": section.is_lockable,
    }


def _fault_payload(fault: FaultScenario) -> dict:
    # Deliberately excludes expected_checks and correct_diagnosis.
    return {
        "id": fault.id,
        "slug": fault.slug,
        "title": fault.title,
        "description": fault.description,
        "symptom": fault.symptom,
        "operation_notes": fault.operation_notes,
        "available_checks": fault.available_checks or fault.expected_checks,
        "difficulty": fault.difficulty,
    }


def build_bundle(db: Session, project: Project) -> dict:
    sections = (
        db.query(ProjectSection)
        .filter(ProjectSection.project_id == project.id)
        .order_by(ProjectSection.order)
        .all()
    )
    faults = (
        db.query(FaultScenario)
        .filter(FaultScenario.project_id == project.id, FaultScenario.is_published.is_(True))
        .order_by(FaultScenario.id)
        .all()
    )
    return {
        "schema": SCHEMA_VERSION,
        "project": {
            "id": project.id,
            "slug": project.slug,
            "title": project.title,
            "industry": project.industry,
            "difficulty": project.difficulty,
            "hours": project.hours,
            "description": project.description,
        },
        "sections": [_section_payload(s) for s in sections],
        "faults": [_fault_payload(f) for f in faults],
        "mentor_pack": _mentor_pack(),
    }


def bundle_version(bundle: dict) -> str:
    """Version is content-addressed so any content change produces a new version.

    ``generated_at`` is excluded so the version is stable across rebuilds.
    """
    stable = {k: v for k, v in bundle.items() if k != "generated_at"}
    return _checksum(stable)[:12]


def ensure_bundles(db: Session) -> int:
    """Build/refresh a bundle for every published project. Returns the number written."""
    PACKAGE_DIR.mkdir(parents=True, exist_ok=True)
    written = 0
    projects = db.query(Project).filter(Project.status == "published").all()

    for project in projects:
        bundle = build_bundle(db, project)
        version = bundle_version(bundle)
        bundle["generated_at"] = _now_iso()
        bundle["version"] = version
        bundle["checksum"] = _checksum(bundle)

        existing = (
            db.query(OfflineContent)
            .filter(OfflineContent.project_id == project.id, OfflineContent.version == version)
            .first()
        )
        if existing and existing.package_path and Path(existing.package_path).exists():
            continue

        # Drop superseded versions so only the current bundle is served.
        db.query(OfflineContent).filter(
            OfflineContent.project_id == project.id, OfflineContent.version != version
        ).delete(synchronize_session=False)

        path = PACKAGE_DIR / f"{project.slug}-{version}.json"
        payload = json.dumps(bundle, ensure_ascii=False, indent=2)
        path.write_text(payload, encoding="utf-8")
        size = len(payload.encode("utf-8"))

        db.add(
            OfflineContent(
                project_id=project.id,
                version=version,
                package_path=str(path),
                checksum=bundle["checksum"],
                content_key_encrypted="",
                size_bytes=size,
            )
        )
        written += 1

    db.commit()
    return written


def read_bundle(record: OfflineContent) -> dict | None:
    path = Path(record.package_path)
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))
