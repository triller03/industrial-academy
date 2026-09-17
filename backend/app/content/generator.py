"""Content & Project Engine.

Every project walks the fixed 17-section engineering lifecycle, mirroring the
deliverable structure of a commissioned industrial control system.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

PROJECT_TEMPLATE: list[dict] = [
    {"key": "project_brief", "title": "Project Brief"},
    {"key": "process_description", "title": "Process Description"},
    {"key": "p_and_id", "title": "P&ID"},
    {"key": "io_list", "title": "I/O List"},
    {"key": "tag_list", "title": "Tag List"},
    {"key": "control_philosophy", "title": "Control Philosophy"},
    {"key": "plc_program", "title": "PLC Program"},
    {"key": "hmi", "title": "HMI"},
    {"key": "scada", "title": "SCADA"},
    {"key": "alarms", "title": "Alarms"},
    {"key": "interlocks", "title": "Interlocks"},
    {"key": "networking", "title": "Networking"},
    {"key": "testing", "title": "Testing"},
    {"key": "fault_injection", "title": "Fault Injection"},
    {"key": "troubleshooting", "title": "Troubleshooting"},
    {"key": "commissioning", "title": "Commissioning"},
    {"key": "final_documentation", "title": "Final Documentation"},
]

SECTION_ORDER = {s["key"]: i for i, s in enumerate(PROJECT_TEMPLATE)}
SECTION_COUNT = len(PROJECT_TEMPLATE)

DIFFICULTY_TIERS = {
    "basic": {"hours": 15, "label": "Basic", "levels": "basic I/O, single loop control"},
    "intermediate": {"hours": 30, "label": "Intermediate", "levels": "cascade control, alarm management"},
    "advanced": {"hours": 50, "label": "Advanced", "levels": "complex sequences, safety interlocks"},
    "expert": {"hours": 80, "label": "Expert", "levels": "safety PLC, model-predictive control"},
}

INDUSTRY_TEMPLATES: dict = {
    "water": {
        "label": "Water & Utilities",
        "equipment": ["centrifugal pumps", "magflow meters", "pressure transmitters", "level transmitters",
                      "chlorine/coagulant dosing pumps", "motorised valves", "backwash filters"],
        "project_types": ["municipal water treatment", "pumping station", "clarifier control", "borehole scheme"],
        "control_strategies": ["PID dosing", "filter backwash sequencing", "pump alternation", "reservoir level control"],
        "faults": [
            "dosing pump over-running downstream demand",
            "filter bed blinding causing rising turbidity",
            "pump on a failed magflow reading",
            "reservoir level transmitter stuck at 4 mA",
        ],
    },
    "mining": {
        "label": "Mining",
        "equipment": ["conveyors", "screens", "thickeners", "slurry pumps", "flotation cells", "vibrating feeders"],
        "project_types": ["conveyor interlock logic", "thickener underflow control", "flotation cell level control"],
        "control_strategies": ["conveyor start/stop sequencing", "density control", "level control with raking"],
        "faults": [
            "conveyor trips on belt misalignment",
            "thickener torque rising unexpectedly",
            "slurry pump cavitates intermittently",
        ],
    },
    "manufacturing": {
        "label": "Manufacturing",
        "equipment": ["VFD drives", "servo actuators", "sensors", "pneumatic cylinders", "vision systems"],
        "project_types": ["packaging line control", "batch mixing", "filling line inspection"],
        "control_strategies": ["sequence control", "recipe management", "reject handling"],
        "faults": [
            "reject station fires on correct parts",
            "filler volume drifts between batches",
            "conveyor handoff jams at high speed",
        ],
    },
}


class ProjectDefinition:
    def __init__(self, slug: str, title: str, industry: str, difficulty: str = "intermediate",
                 hours: int | None = None, description: str = ""):
        self.slug = slug
        self.title = title
        self.industry = industry
        self.difficulty = difficulty
        self.hours = hours or DIFFICULTY_TIERS.get(difficulty, DIFFICULTY_TIERS["intermediate"])["hours"]
        self.description = description
        self.sections: list[dict] = []
        self.faults: list[dict] = []

    def add_section(self, key: str, title: str, content: str) -> "ProjectDefinition":
        self.sections.append({"key": key, "title": title, "content": content})
        self.sections.sort(key=lambda s: SECTION_ORDER.get(s["key"], 99))
        return self

    def add_fault(self, fault: dict) -> "ProjectDefinition":
        self.faults.append(fault)
        return self


def slugify(text: str) -> str:
    lowered = text.lower().strip()
    lowered = re.sub(r"[^a-z0-9]+", "-", lowered)
    return lowered.strip("-")


def make_brief(industry: str, title: str, project_type: str, scope: str) -> str:
    return (
        f"# {title} — Client Brief\n\n"
        f"**Industry:** {INDUSTRY_TEMPLATES[industry]['label']}\n\n"
        f"**Scope:** {project_type.capitalize()} — {scope}\n\n"
        "## Client Requirements\n"
        "- Operate reliably under the site's power and connectivity conditions.\n"
        "- Provide local (HMI) and supervisory (SCADA) visibility of the process.\n"
        "- Fail safe on loss of instrument signal or communications.\n"
        "- Include comprehensive alarm and interlock behaviour, documented per section.\n\n"
        "## Deliverables\n"
        "A completed engineering package covering all 17 lifecycle sections, "
        "from P&ID and I/O list through commissioning and final documentation."
    )


class ProjectGenerator:
    """Generates the 17-section engineering package for a project definition.

    In production this would call an LLM with structured prompting for narrative
    sections; the deterministic scaffolding (structure, I/O, tag lists) is built
    here. Mandatory engineering review remains a human gate for every published project.
    """

    def __init__(self, definition: ProjectDefinition):
        self.definition = definition

    def build_sections(self, fault_list: list[dict] | None = None) -> list[dict]:
        d = self.definition
        ind = INDUSTRY_TEMPLATES.get(d.industry, INDUSTRY_TEMPLATES["water"])
        tier = DIFFICULTY_TIERS.get(d.difficulty, DIFFICULTY_TIERS["intermediate"])

        sections = [
            self._s("project_brief", "Project Brief", make_brief(d.industry, d.title, ind["project_types"][0], d.description)),
            self._s("process_description", "Process Description",
                    f"# Process Description\n\nThe plant operates as a continuous {ind['project_types'][0]} process. "
                    f"Core equipment: {', '.join(ind['equipment'][:4])}. "
                    f"Primary control strategies: {', '.join(ind['control_strategies'][:3])}.\n\n"
                    "This section defines the process in plain engineering terms before any control detail. "
                    "A control engineer should be able to draw the process from this description alone."),
            self._s("p_and_id", "P&ID",
                    "# P&ID\n\nReference symbology: ISA-5.1. "
                    "Instrument tags follow the loop convention (e.g. LT-001, PT-002). "
                    "[Drawing placeholder — see seed content for the flagship project's full P&ID.]"),
            self._s("io_list", "I/O List",
                    "# I/O List\n\n"
                    "| Tag | Type | Description | Address |\n"
                    "|-----|------|-------------|---------|\n"
                    "| LT-001 | AI | Level transmitter, 4-20 mA | IW0.0 |\n"
                    "| LT-001 | AI | Level transmitter, 4-20 mA | IW0.0 |\n"
                    "| FT-001 | AI | Flow transmitter, 4-20 mA | IW0.2 |\n"
                    "| PT-001 | AI | Pressure transmitter | IW0.4 |\n"
                    "| M-001 RUN | DI | Pump motor running feedback | I1.0 |\n"
                    "| M-001 CMD | DO | Pump motor command | Q0.0 |\n"
                    "| ESD | DI | Emergency stop | I1.6 |"),
            self._s("tag_list", "Tag List",
                    "# Tag List\n\nEvery physical and logical tag used across the project, with data "
                    "types and engineering units. This is the single source of truth for the PLC program, "
                    "HMI and SCADA layers."),
            self._s("control_philosophy", "Control Philosophy",
                    f"# Control Philosophy\n\n"
                    f"Primary strategies: {', '.join(ind['control_strategies'])}.\n\n"
                    "Modes: AUTO / MAN / LOCAL. On loss of communications the loop defaults to a safe "
                    "state defined per tag. This section defines setpoint ranges, ramp rates, and "
                    "the behaviour of every loop under normal and abnormal conditions."),
            self._s("plc_program", "PLC Program",
                    "# PLC Program\n\nProgramming standard: IEC 61131-3, Siemens TIA Portal. "
                    "Function blocks are named per the tag list. Commentary references the control "
                    "philosophy section for every block that affects safety."),
            self._s("hmi", "HMI",
                    "# HMI\n\nOperator screens: overview, area pages, alarm summary, trend pages. "
                    "Navigation flows are defined so an operator never clicks more than three times "
                    "to reach any alarm of interest."),
            self._s("scada", "SCADA",
                    "# SCADA\n\nSupervisory layer (WinCC) providing trends, historical archiving, "
                    "and remote monitoring. Historian tags mirror the tag list. Alarms also surface here."),
            self._s("alarms", "Alarms",
                    "# Alarms\n\nEvery alarm has: a tag, a setpoint, a priority, a message, and an owner. "
                    "Alarm rationalisation follows ISA-18.2. No alarm may be configured without a documented "
                    "operator action."),
            self._s("interlocks", "Interlocks",
                    "# Interlocks\n\nPermissives and interlocks are listed with the cause-and-effect "
                    "matrix. Safety interlocks (ESD, LOTO permissive) are hardwired and de-energise-to-trip. "
                    "The interlock list is the checklist and the HMI interlock page shows the reason a "
                    "start command is being held off."),
            self._s("networking", "Networking",
                    "# Networking\n\nPROFINET as the real-time control network, plant network segmented "
                    "from the office network. IP scheme, subnetting, and device roles are documented "
                    "for commissioning and fault finding."),
            self._s("testing", "Testing",
                    "# Testing\n\nFAT and SAT covered per section. Each test has a numbered procedure, "
                    "expected result, and sign-off. No project section is complete until its tests pass "
                    "with evidence."),
            self._s("fault_injection", "Fault Injection",
                    "# Fault Injection\n\n" + self._fault_injection_text(fault_list)),
            self._s("troubleshooting", "Troubleshooting",
                    "# Troubleshooting\n\nDiagnostic trees live in the Decision Trees module. The "
                    "systematic sequence is: verify instrument power -> verify signal -> verify command "
                    "-> verify actuation -> verify permissive."),
            self._s("commissioning", "Commissioning",
                    "# Commissioning\n\nSequenced pre-commissioning checks, functional tests, and "
                    "handover criteria. Includes instrument calibration records, loop checks, and a "
                    "site acceptance test."),
            self._s("final_documentation", "Final Documentation",
                    "# Final Documentation\n\nAs-built drawings, final I/O and tag lists, test certificates, "
                    "training records, and the operations & maintenance (O&M) manual. This folder is the "
                    "student's professional work sample."),
        ]
        return sections

    def _fault_injection_text(self, fault_list: list[dict] | None) -> str:
        if not fault_list:
            return (
                "Fault scenarios are injected into the working simulation by the Fault Injection engine. "
                "Each scenario defines the symptom the operator would observe, the checks available, and "
                "the correct diagnosis. Generated content is seeded per project."
            )
        lines = ["The fault-injection module offers these scenarios for this project:"]
        for idx, f in enumerate(fault_list, start=1):
            lines.append(f"{idx}. **{f['title']}** — symptom: _{f['symptom']}_. Diagnosis: {f['correct_diagnosis']}.")
        return "# Fault Injection\n\n" + "\n".join(lines)

    def _s(self, key: str, title: str, content: str) -> dict:
        return {"key": key, "title": title, "content": content}

    def export_json(self, fault_list: list[dict] | None = None) -> dict:
        d = self.definition
        return {
            "slug": d.slug,
            "title": d.title,
            "industry": d.industry,
            "difficulty": d.difficulty,
            "hours": d.hours,
            "description": d.description,
            "sections": self.build_sections(fault_list),
            "faults": [dict(f) for f in (fault_list or [])],
        }

    def export_to_disk(self, root: str | Path) -> Path:
        """Materialise the 17-folder structure a student's completed project looks like."""
        root = Path(root)
        base = root / self.definition.slug
        base.mkdir(parents=True, exist_ok=True)
        manifest = {"slug": self.definition.slug, "title": self.definition.title, "version": "1.0.0", "sections": {}}
        for section in self.build_sections():
            folder = base / f"{SECTION_ORDER[section['key']]:02d}_{section['key'].lower()}"
            folder.mkdir(exist_ok=True)
            (folder / "README.md").write_text(section["content"], encoding="utf-8")
            manifest["sections"][section["key"]] = {"title": section["title"], "path": folder.name}
        (base / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        return base