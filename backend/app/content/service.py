"""Template-based project generation and persistence.

In production the narrative sections would come from an LLM; the deterministic
scaffolding (structure, I/O, tag lists, fault scenarios, grading set) is built
here so any generated project is immediately learnable and gradeable with the
same fault engine as seeded content. Generation is an admin action; the audit
trail records each project.
"""

from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from app.activity import log_activity
from app.content import INDUSTRY_TEMPLATES, ProjectDefinition, ProjectGenerator, slugify
from app.fault.palette import palette
from app.models import FaultScenario, Project, ProjectSection

GENERIC_EXPECTED_CHECKS: list[str] = [
    "verify_instrument_power",
    "verify_signal_reading",
    "verify_command",
    "verify_actuation",
    "verify_permissive",
    "review_alarm_history",
]

GENERIC_MISDIAGNOSES: list[str] = [
    "power supply",
    "instrument calibration",
    "controller software",
]


def build_fault_dicts(industry: str, project_slug: str) -> list[dict]:
    template = INDUSTRY_TEMPLATES.get(industry, INDUSTRY_TEMPLATES["water"])
    faults: list[dict] = []
    for raw in template["faults"]:
        title = raw.strip().capitalize()
        words = [w for w in raw.lower().replace("-", " ").split() if len(w) > 2]
        faults.append(
            {
                "slug": f"{project_slug}-{slugify(raw)[:36]}",
                "title": title,
                "symptom": (
                    f"{title} observed in the running simulation; the affected loop shows "
                    "the first deviation from normal operation."
                ),
                "description": f"Generated scenario for {template['label']}: {raw}.",
                "injected_fault": raw,
                "operation_notes": (
                    "Scaffold content produced by the content generator; it grades with the "
                    "standard check set. Reword the narrative before production use."
                ),
                "expected_checks": list(GENERIC_EXPECTED_CHECKS),
                "correct_diagnosis": title,
                "correct_diagnosis_keys": words[:6] or [project_slug],
                "common_misdiagnoses": list(GENERIC_MISDIAGNOSES),
            }
        )
    return faults


def persist_generated_project(
    db: Session,
    industry: str,
    title: str,
    difficulty: str = "intermediate",
    description: str = "",
    actor_user_id: int | None = None,
) -> Project:
    """Build a full 17-section project from the industry template and publish it."""
    cleaned_title = title.strip() or "Generated Project"
    base_slug = slugify(cleaned_title) or "generated-project"
    slug = f"{base_slug}-{uuid.uuid4().hex[:6]}"

    definition = ProjectDefinition(
        slug=slug,
        title=cleaned_title,
        industry=industry,
        difficulty=difficulty,
        description=description.strip(),
    )
    faults = build_fault_dicts(industry, slug)
    generator = ProjectGenerator(definition)

    project = Project(
        slug=slug,
        title=cleaned_title,
        industry=industry,
        difficulty=difficulty,
        hours=definition.hours,
        description=definition.description,
        status="published",
    )
    db.add(project)
    db.flush()

    for i, section in enumerate(generator.build_sections(faults)):
        db.add(
            ProjectSection(
                project_id=project.id,
                order=i,
                key=section["key"],
                title=section["title"],
                content=section["content"],
            )
        )

    for f in faults:
        db.add(
            FaultScenario(
                project_id=project.id,
                slug=f["slug"],
                title=f["title"],
                description=f["description"],
                symptom=f["symptom"],
                injected_fault=f["injected_fault"],
                operation_notes=f["operation_notes"],
                available_checks=palette(f["expected_checks"]),
                expected_checks=f["expected_checks"],
                correct_diagnosis=f["correct_diagnosis"],
                correct_diagnosis_keys=f["correct_diagnosis_keys"],
                common_misdiagnoses=f["common_misdiagnoses"],
                difficulty=2,
                is_published=True,
            )
        )

    if actor_user_id is not None:
        log_activity(
            db,
            actor_user_id,
            "project.generate",
            entity=f"project:{slug}",
            detail={"industry": industry, "title": cleaned_title, "faults": len(faults)},
        )

    db.commit()
    return project