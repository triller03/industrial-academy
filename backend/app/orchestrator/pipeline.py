"""Orchestration pipeline: the ordered engineering workflow a project is driven through.

The blueprint calls for an "orchestration engine with a per-project workflow
state machine" instead of a flat section list. Each stage names the discipline,
the desktop tool it is associated with (TIA Portal, WinCC, Factory I/O), the
deliverable and the gate licence the student needs.

Stages are intentionally coarse (the per-discipline section structure lives
inside the project content); the pipeline is the *state machine* you advance as
you drive the project through the real tools.
"""

from __future__ import annotations

PIPELINE: list[dict] = [
    {
        "key": "kickoff",
        "label": "Kickoff & scope",
        "tool": None,
        "deliverable": "Engineering scope, I/O estimate, safety philosophy",
        "gate": None,
    },
    {
        "key": "engineering",
        "label": "Engineering (FRS / P&ID)",
        "tool": "wincc",
        "deliverable": "Functional requirement spec, P&ID, tag list",
        "gate": "can_schematic_viewer",
    },
    {
        "key": "schematic",
        "label": "Electrical schematic",
        "tool": None,
        "deliverable": "IEC 61346-style schematics, wiring list",
        "gate": "can_schematic_viewer",
    },
    {
        "key": "plc",
        "label": "PLC & TIA Portal",
        "tool": "tia",
        "deliverable": "IEC 61131-3 blocks, SCL, tag import",
        "gate": "can_tia_bridge",
    },
    {
        "key": "hmi",
        "label": "HMI & WinCC",
        "tool": "wincc",
        "deliverable": "Unified SCADA screens, alarms, user access",
        "gate": "can_tia_bridge",
    },
    {
        "key": "simulation",
        "label": "Simulation & Factory I/O",
        "tool": "factoryio",
        "deliverable": "Logic-in-the-loop commissioning, fault scenarios",
        "gate": None,
    },
    {
        "key": "handover",
        "label": "Commissioning & handover",
        "tool": None,
        "deliverable": "Acceptance record, portfolio entry, certificate",
        "gate": None,
    },
]

STAGE_INDEX = {stage["key"]: i for i, stage in enumerate(PIPELINE)}


def pipeline() -> list[dict]:
    return [dict(s) for s in PIPELINE]


def stage_at(index: int) -> dict:
    idx = max(0, min(index, len(PIPELINE) - 1))
    return dict(PIPELINE[idx])


def previous_stage(index: int, *, step: int = 1) -> int:
    return max(0, index - step)


def next_stage(index: int, *, step: int = 1) -> int:
    return min(len(PIPELINE) - 1, index + step)


def stage_key(index: int) -> str:
    return PIPELINE[max(0, min(index, len(PIPELINE) - 1))]["key"]